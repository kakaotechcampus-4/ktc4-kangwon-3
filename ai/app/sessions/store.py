"""진단 세션을 상품 단위로 메모리에 보관하는 저장소.

AI 재시작 시 세션은 사라짐. 실행기·라우터 등 여러 스레드가 함께 쓰므로 모든 변경은 잠금 안에서 처리.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from ..config import AWAITING_INPUT_RETENTION_SECONDS, SESSION_RETENTION_SECONDS
from ..observability.context import ExecutionContext, PipelineStage, RunType
from ..schemas.agent import ExtractionInput
from ..schemas.base import utc_now
from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import ExecutionEndReason, FinalAssessment
from ..schemas.session import DiagnosisSession, SessionAnswer, SessionStatus

# 진행 중으로 보는 상태. 같은 상품의 새 접수를 막음
ACTIVE_STATUSES = frozenset({SessionStatus.ACCEPTED, SessionStatus.RUNNING, SessionStatus.AWAITING_INPUT})


class SessionConflictError(RuntimeError):
    """진행 중인 상품이 요청에 섞여 있어 접수를 거절한 경우.

    Attributes:
        product_ids: 이미 진행 중인 상품 ID 목록.
    """

    def __init__(self, product_ids: list[str]) -> None:
        super().__init__(f"이미 진행 중인 상품이 있습니다: {', '.join(product_ids)}")
        self.product_ids = product_ids


class SessionNotFoundError(LookupError):
    """재진단할 세션이 없는 경우. AI 재시작·정리로 사라진 세션 포함."""


class ResumeConflictError(RuntimeError):
    """답변 대기가 아니거나, 요청이 기다리는 질문(실행·회차·진단서)과 맞지 않는 경우. 중복·늦게 온 답변."""


class UnknownQuestionKeyError(ValueError):
    """이번 회차에 묻지 않은 질문의 답변이 섞인 경우.

    Attributes:
        question_keys: 묻지 않은 질문 키 목록.
    """

    def __init__(self, question_keys: list[str]) -> None:
        super().__init__(f"이번 회차에 묻지 않은 질문입니다: {', '.join(question_keys)}")
        self.question_keys = question_keys


class SessionStore:
    """상품 ID를 세션 ID로 쓰는 진단 세션 저장소."""

    def __init__(
        self,
        *,
        retention: timedelta = timedelta(seconds=SESSION_RETENTION_SECONDS),
        awaiting_retention: timedelta = timedelta(seconds=AWAITING_INPUT_RETENTION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """저장소를 만든다.

        Args:
            retention: 종료된 세션 보관 시간.
            awaiting_retention: 답변 대기 세션 보관 시간. 지나면 지워져 재진단은 세션 없음(404).
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
        """
        self._sessions: dict[str, DiagnosisSession] = {}
        self._lock = Lock()
        # 상태별 보관 시간. 정리 대상 상태를 늘리면 여기만 추가
        self._retention_by_status = {
            SessionStatus.COMPLETED: retention,
            SessionStatus.FAILED: retention,
            SessionStatus.AWAITING_INPUT: awaiting_retention,
        }
        self._clock = clock

    def accept(self, diagnosis_id: str, inputs: list[ExtractionInput]) -> list[DiagnosisSession]:
        """진단서 한 건의 상품들을 세션으로 접수한다.

        하나라도 진행 중이면 아무것도 접수하지 않고 전체를 거절함 (#263).
        완료·실패한 상품은 새 세션으로 교체. 입력은 재진단용으로 세션에 보관.

        Args:
            diagnosis_id: BE 진단서 ID.
            inputs: 접수할 상품별 입력. product_id가 세션 ID.

        Returns:
            list[DiagnosisSession]: 접수된 세션. inputs 순서와 같음.

        Raises:
            SessionConflictError: 진행 중인 상품이 하나라도 있는 경우.
        """
        with self._lock:
            conflicts = [
                item.product_id for item in inputs
                if (session := self._sessions.get(item.product_id)) and session.status in ACTIVE_STATUSES
            ]
            if conflicts:
                raise SessionConflictError(conflicts)

            now = self._clock()
            accepted = []
            for item in inputs:
                context = ExecutionContext.start(
                    product_id=item.product_id, run_type=RunType.PRODUCTION, diagnosis_id=diagnosis_id,
                )
                session = DiagnosisSession(context=context, source=item, accepted_at=now, updated_at=now)
                self._sessions[item.product_id] = session
                accepted.append(session)
            return accepted

    def resume(
        self,
        *,
        diagnosis_id: str,
        product_id: str,
        run_id: str,
        question_round: int,
        answers: dict[str, str],
    ) -> DiagnosisSession:
        """답변 대기 세션에 답변을 더해 새 실행으로 다시 접수한다 (#310).

        원래 입력·이전 결과·질문은 그대로 두고, 새 run_id로 접수 상태가 됨.
        시간 초과 기준(accepted_at)은 재접수 시각부터. 답하지 않은 질문은 허용.

        Args:
            diagnosis_id: BE 진단서 ID. 세션과 같아야 함.
            product_id: 세션 ID (상품 ID).
            run_id: 질문으로 끝난 실행 ID. 지금 세션의 실행과 같아야 함.
            question_round: 답하는 질문 회차. 지금 기다리는 회차와 같아야 함.
            answers: 질문 키 → 답변.

        Returns:
            DiagnosisSession: 재접수된 세션.

        Raises:
            SessionNotFoundError: 세션이 없는 경우.
            ResumeConflictError: 답변 대기가 아니거나 실행·회차·진단서가 다른 경우.
            UnknownQuestionKeyError: 이번 회차에 묻지 않은 질문 키가 있는 경우.
        """
        with self._lock:
            session = self._sessions.get(product_id)
            if session is None:
                raise SessionNotFoundError(f"세션이 없습니다: {product_id}")
            if session.status is not SessionStatus.AWAITING_INPUT:
                raise ResumeConflictError(f"답변 대기 상태가 아닙니다: {product_id} ({session.status})")
            expected = (session.context.diagnosis_id, session.context.run_id, session.question_round)
            if (diagnosis_id, run_id, question_round) != expected:
                raise ResumeConflictError(f"기다리는 질문과 다른 답변입니다: {product_id}")
            asked = {question.question_key for question in session.questions}
            unknown = [key for key in answers if key not in asked]
            if unknown:
                raise UnknownQuestionKeyError(unknown)

            now = self._clock()
            context = ExecutionContext.start(
                product_id=product_id, run_type=session.context.run_type, diagnosis_id=diagnosis_id,
            )
            new_answers = [
                SessionAnswer(question_round=question_round, question_key=key, answer_text=text)
                for key, text in answers.items()
            ]
            resumed = DiagnosisSession.model_validate({
                **dict(session),
                "context": context,
                "status": SessionStatus.ACCEPTED,
                "stage": None,
                "stage_started_at": None,
                "termination_reason": None,
                "answers": [*session.answers, *new_answers],
                "accepted_at": now,
                "updated_at": now,
            })
            self._sessions[product_id] = resumed
            return resumed

    def get(self, product_id: str) -> DiagnosisSession | None:
        """세션을 조회한다.

        Args:
            product_id: 세션 ID (상품 ID).

        Returns:
            DiagnosisSession | None: 세션. 없거나 정리됐으면 None.
        """
        with self._lock:
            return self._sessions.get(product_id)

    def unfinished(self) -> list[DiagnosisSession]:
        """접수·실행 중인 세션 목록. 답변 대기는 실행이 끝난 상태라 제외.

        Returns:
            list[DiagnosisSession]: 접수 또는 실행 중인 세션.
        """
        with self._lock:
            return [
                session for session in self._sessions.values()
                if session.status in {SessionStatus.ACCEPTED, SessionStatus.RUNNING}
            ]

    def start(self, context: ExecutionContext) -> DiagnosisSession | None:
        """접수된 세션을 실행 중으로 바꾼다.

        Args:
            context: 이 실행의 컨텍스트. 세션의 run_id와 같을 때만 바꿈.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 접수 상태가 아니거나(이미 시간 초과로 실패 등)
                다른 실행의 세션이면 None.
        """
        return self._transition(context, {SessionStatus.ACCEPTED}, status=SessionStatus.RUNNING)

    def update_stage(self, context: ExecutionContext, stage: PipelineStage) -> DiagnosisSession | None:
        """실행 중인 세션의 현재 단계를 기록한다.

        Args:
            context: 이 실행의 컨텍스트. 세션의 run_id와 같을 때만 바꿈.
            stage: 새 단계.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 실행 중이 아니거나 다른 실행의 세션이면 None.
        """
        return self._transition(
            context, {SessionStatus.RUNNING}, stage=stage, stage_started_at=self._clock(),
        )

    def finish(
        self,
        context: ExecutionContext,
        result: FinalAssessment,
        questions: list[PublicQuestionDto] | None = None,
    ) -> DiagnosisSession | None:
        """실행 결과를 기록한다.

        종료 사유가 user_input_required면 답변 대기(질문 회차 1 증가), 그 외는 완료로 둠.

        Args:
            context: 이 실행의 컨텍스트. 세션의 run_id와 같을 때만 바꿈.
            result: 파이프라인 최종 결과.
            questions: 답변 대기로 끝날 때 보낼 질문. 완료면 무시.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 실행 중이 아니거나(시간 초과로 이미 실패 등)
                재접수로 다른 실행의 세션이면 None. 늦게 끝난 결과 무시용.

        Raises:
            ValueError: 답변 대기로 끝나는데 질문이 없는 경우.
        """
        if result.termination_reason is not ExecutionEndReason.USER_INPUT_REQUIRED:
            return self._transition(
                context, {SessionStatus.RUNNING},
                status=SessionStatus.COMPLETED, termination_reason=result.termination_reason, result=result,
            )
        if not questions:
            raise ValueError("답변 대기로 끝나는 결과에는 질문이 필요합니다.")
        return self._transition(
            context, {SessionStatus.RUNNING},
            derive=lambda session: {"question_round": session.question_round + 1},
            status=SessionStatus.AWAITING_INPUT, termination_reason=result.termination_reason, result=result,
            questions=list(questions),
        )

    def fail(self, context: ExecutionContext, *, error_code: str, retryable: bool) -> DiagnosisSession | None:
        """접수·실행 중인 세션을 실패로 끝낸다.

        종료 사유로 바꾸지 않고 오류 코드로만 기록함 (#171 §7.1.1).

        Args:
            context: 이 실행의 컨텍스트. 세션의 run_id와 같을 때만 바꿈.
            error_code: 실패 코드.
            retryable: 같은 요청을 다시 보내 복구 가능한지.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 이미 끝났거나 다른 실행의 세션이면 None.
        """
        return self._transition(
            context, {SessionStatus.ACCEPTED, SessionStatus.RUNNING},
            status=SessionStatus.FAILED, error_code=error_code, retryable=retryable,
        )

    def purge(self) -> int:
        """보관 시간이 지난 종료·답변 대기 세션을 지운다. 접수·실행 중 세션은 시간 초과 처리가 맡음.

        보관 시간은 마지막 상태 변경(updated_at)부터. 답변 대기는 질문을 보낸 시각부터.

        Returns:
            int: 지운 세션 수.
        """
        with self._lock:
            now = self._clock()
            expired = [
                product_id for product_id, session in self._sessions.items()
                if (retention := self._retention_by_status.get(session.status)) is not None
                and session.updated_at <= now - retention
            ]
            for product_id in expired:
                del self._sessions[product_id]
            return len(expired)

    def _transition(
        self,
        context: ExecutionContext,
        allowed: set[SessionStatus],
        derive: Callable[[DiagnosisSession], dict[str, Any]] | None = None,
        **changes: Any,
    ) -> DiagnosisSession | None:
        """같은 실행(run_id)의 세션이 허용된 상태일 때만 바꾼다. 바꾼 세션은 새 객체로 교체.

        derive는 지금 세션 값으로 계산하는 변경(회차 증가 등). 잠금 안에서 부름.
        """
        product_id = context.product_id
        with self._lock:
            session = self._sessions.get(product_id)
            if session is None or session.status not in allowed:
                return None
            # 시간 초과 뒤 재접수되면 같은 상품에 새 세션이 생김. 옛 실행의 늦은 갱신은 무시
            if session.context.run_id != context.run_id:
                return None
            # 검증(UTC 정규화 등)을 다시 거치도록 model_copy 대신 새로 만듦
            derived = derive(session) if derive else {}
            updated = DiagnosisSession.model_validate(
                {**dict(session), **changes, **derived, "updated_at": self._clock()},
            )
            self._sessions[product_id] = updated
            return updated
