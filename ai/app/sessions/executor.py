"""접수한 진단 세션을 실행 상한 안에서 백그라운드로 실행.

에이전트 호출이 동기라 스레드 풀 사용. 실행할 진단 함수는 주입식 (파이프라인 러너 연결 전).
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from typing import Literal, Protocol
from uuid import uuid4

from ..config import (
    MAX_DEV_INFLIGHT_SESSIONS, MAX_INFLIGHT_SESSIONS, MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS,
)
from ..errors import AIResponseCode
from ..observability.context import ExecutionContext, PipelineStage, RunType
from ..schemas.agent import ExtractionInput
from ..schemas.base import utc_now
from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import ExecutionEndReason, FinalAssessment, FinalVerificationStatus, ToolName
from ..schemas.session import DiagnosisInput, DiagnosisSession, SessionStatus
from .store import SessionStore

logger = logging.getLogger(__name__)

# Tool 진행 상태. Tool 실행 오류도 completed (실패 여부는 분야 카드에서 표시)
ToolProgressStatus = Literal["started", "completed", "skipped"]


class ProgressReporter(Protocol):
    """진단 함수가 부르는 진행 알림. 단계 변경과 Tool 진행은 서로 다른 경로."""

    def stage(self, stage: PipelineStage) -> None: ...

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None: ...


# 실행 입력(원래 입력 + 재진단이면 이전 결과·답변), 실행 컨텍스트, 진행 알림을 받아 최종 결과를 돌려주는 진단 함수
DiagnosisJob = Callable[[DiagnosisInput, ExecutionContext, ProgressReporter], FinalAssessment]
# 답변 대기로 끝난 결과를 BE에 보낼 질문으로 바꾸는 함수. 결과는 세션에 기록돼 질문 콜백·답변 검사에 쓰임
QuestionBuilder = Callable[[FinalAssessment], list[PublicQuestionDto]]
# 세션 상태가 바뀔 때마다 호출. 이후 콜백 전송기 자리
SessionListener = Callable[[DiagnosisSession], None]
# Tool 진행마다 호출. 세션 상태는 바뀌지 않아 그 시점 세션을 같이 전달
ToolListener = Callable[[DiagnosisSession, ToolName, ToolProgressStatus], None]


class QueueFullError(RuntimeError):
    """대기 + 실행 중 세션이 상한을 넘어 접수를 거절한 경우."""


# 사용자에게 질문하는 최대 회차 (#310). 넘으면 질문 대신 미완료 결과로 끝냄
MAX_QUESTION_ROUNDS = 2
# 질문 회차를 다 쓰고 미완료로 끝낼 때 결과에 붙이는 안내 (공개 진단서 notices로 나감)
QUESTION_LIMIT_NOTICE = "추가 확인이 필요한 정보가 남아 있어 진단을 끝까지 마치지 못했습니다. 판매 전 직접 확인이 필요합니다."


def _close_at_question_limit(result: FinalAssessment, context: ExecutionContext) -> FinalAssessment:
    """질문 회차를 다 쓴 실행의 질문 결과를 미완료 결과로 바꾼다. 남은 질문은 기록용으로 그대로 둠."""
    logger.warning(
        "질문 회차 초과로 미완료 처리 (product_id=%s, run_id=%s, 남은 질문 %d개)",
        context.product_id, context.run_id, len(result.follow_up_questions),
    )
    return result.model_copy(update={
        "termination_reason": ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
        "missing_information": [*result.missing_information, QUESTION_LIMIT_NOTICE],
    })


class _Progress:
    """세션 하나의 진행 알림. 저장소 갱신 후 구독자에게 전달. 자기 실행(run_id)의 세션만 갱신."""

    def __init__(self, executor: "SessionExecutor", context: ExecutionContext) -> None:
        self._executor = executor
        self._context = context

    def stage(self, stage: PipelineStage) -> None:
        self._executor._publish(self._executor.store.update_stage(self._context, stage))

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        # 저장소는 바꾸지 않음. 시간 초과·재접수로 이 실행이 끝났으면 알리지 않음
        session = self._executor.store.get(self._context.product_id)
        if (session is None or session.context.run_id != self._context.run_id
                or session.status is not SessionStatus.RUNNING):
            return
        self._executor._publish_tool(session, tool_name, status)


class SessionExecutor:
    """세션을 접수해 진단 함수를 백그라운드로 실행한다."""

    def __init__(
        self,
        store: SessionStore,
        job: DiagnosisJob,
        *,
        questions: QuestionBuilder,
        max_running: int = MAX_RUNNING_SESSIONS,
        max_inflight: int = MAX_INFLIGHT_SESSIONS,
        max_dev_inflight: int = MAX_DEV_INFLIGHT_SESSIONS,
        max_duration: timedelta = timedelta(seconds=SESSION_MAX_DURATION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """실행기를 만든다.

        Args:
            store: 세션 저장소.
            job: 실행할 진단 함수.
            questions: 답변 대기 결과의 질문 변환 함수.
            max_running: 동시 실행 상한.
            max_inflight: 대기 + 실행 중 세션 상한.
            max_dev_inflight: 개발용 진단의 대기 + 실행 중 상한. 전체 상한에도 같이 셈.
            max_duration: 접수부터 결과까지 최대 시간.
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
        """
        self.store = store
        self._job = job
        self._questions = questions
        self._pool = ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="diagnosis")
        self._max_inflight = max_inflight
        self._max_dev_inflight = max_dev_inflight
        self._max_duration = max_duration
        self._clock = clock
        self._listeners: list[SessionListener] = []
        self._tool_listeners: list[ToolListener] = []
        self._lock = Lock()
        self._inflight = 0
        # 실행 중인 개발용 진단의 run_id. 끝나면 개발용 자리도 반납
        self._dev_runs: set[str] = set()

    def subscribe(self, listener: SessionListener) -> None:
        """세션 상태가 바뀔 때마다 부를 함수를 등록한다.

        Args:
            listener: 바뀐 세션을 받는 함수.
        """
        self._listeners.append(listener)

    def subscribe_tool(self, listener: ToolListener) -> None:
        """Tool 진행(시작·완료·건너뜀)마다 부를 함수를 등록한다. 단계 변경과 따로 받음.

        Args:
            listener: (그 시점 세션, Tool 이름, 진행 상태)를 받는 함수.
        """
        self._tool_listeners.append(listener)

    def submit(self, diagnosis_id: str, inputs: list[ExtractionInput]) -> list[DiagnosisSession]:
        """상품들을 세션으로 접수하고 백그라운드 실행을 예약한다.

        Args:
            diagnosis_id: BE 진단서 ID.
            inputs: 상품별 입력. product_id가 세션 ID.

        Returns:
            list[DiagnosisSession]: 접수된 세션.

        Raises:
            QueueFullError: 대기 + 실행 중 세션이 상한을 넘는 경우.
            SessionConflictError: 진행 중인 상품이 섞인 경우.
        """
        with self._lock:
            if self._inflight + len(inputs) > self._max_inflight:
                raise QueueFullError(
                    f"진단 대기열이 가득 찼습니다 ({self._inflight}/{self._max_inflight})."
                )
            sessions = self.store.accept(diagnosis_id, inputs)
            self._inflight += len(inputs)

        for session in sessions:
            self._pool.submit(self._run, session.context)
        return sessions

    def resume(
        self,
        *,
        diagnosis_id: str,
        product_id: str,
        run_id: str,
        question_round: int,
        answers: dict[str, str],
    ) -> DiagnosisSession:
        """답변 대기 세션을 답변과 함께 재접수하고 새 실행을 예약한다. 접수와 같은 대기열·상한 사용.

        Args:
            diagnosis_id: BE 진단서 ID.
            product_id: 세션 ID (상품 ID).
            run_id: 질문으로 끝난 실행 ID.
            question_round: 답하는 질문 회차.
            answers: 질문 키 → 답변.

        Returns:
            DiagnosisSession: 재접수된 세션. context.run_id가 새 실행 ID.

        Raises:
            QueueFullError: 대기 + 실행 중 세션이 상한을 넘는 경우.
            SessionNotFoundError: 세션이 없는 경우.
            ResumeConflictError: 답변 대기가 아니거나 실행·회차·진단서가 다른 경우.
            UnknownQuestionKeyError: 이번 회차에 묻지 않은 질문 키가 있는 경우.
        """
        with self._lock:
            if self._inflight + 1 > self._max_inflight:
                raise QueueFullError(
                    f"진단 대기열이 가득 찼습니다 ({self._inflight}/{self._max_inflight})."
                )
            session = self.store.resume(
                diagnosis_id=diagnosis_id, product_id=product_id, run_id=run_id,
                question_round=question_round, answers=answers,
            )
            self._inflight += 1

        self._pool.submit(self._run, session.context)
        return session

    def submit_dev(self, item: ExtractionInput) -> DiagnosisSession:
        """개발용 진단 한 건을 접수한다. 진단서 없이 접수해 콜백은 나가지 않음.

        상품 ID는 운영 상품과 겹치지 않게 dev- 접두어로 새로 발급하고, 입력의 product_id는 쓰지 않음.

        Args:
            item: 상품 입력.

        Returns:
            DiagnosisSession: 접수된 세션. 상품 ID는 발급한 dev- ID.

        Raises:
            QueueFullError: 개발용 상한 또는 전체 상한을 넘는 경우.
        """
        product_id = f"dev-{uuid4()}"
        item = item.model_copy(update={"product_id": product_id})
        with self._lock:
            if len(self._dev_runs) >= self._max_dev_inflight:
                raise QueueFullError(
                    f"개발용 진단 대기열이 가득 찼습니다 ({len(self._dev_runs)}/{self._max_dev_inflight})."
                )
            if self._inflight + 1 > self._max_inflight:
                raise QueueFullError(
                    f"진단 대기열이 가득 찼습니다 ({self._inflight}/{self._max_inflight})."
                )
            [session] = self.store.accept(None, [item], run_type=RunType.TEST)
            self._inflight += 1
            self._dev_runs.add(session.context.run_id)

        self._pool.submit(self._run, session.context)
        return session

    def expire_overdue(self) -> int:
        """접수부터 최대 시간을 넘긴 세션을 시간 초과 실패로 끝낸다.

        실행 중인 스레드는 멈출 수 없어서, 나중에 결과가 와도 저장소가 무시함.

        Returns:
            int: 실패로 바꾼 세션 수.
        """
        deadline = self._clock() - self._max_duration
        expired = 0
        for session in self.store.unfinished():
            if session.accepted_at > deadline:
                continue
            failed = self.store.fail(
                session.context, error_code=AIResponseCode.TIMEOUT.value.code, retryable=True,
            )
            if failed is not None:
                expired += 1
                self._publish(failed)
        return expired

    def shutdown(self, *, wait: bool = False) -> None:
        """새 실행을 받지 않고 실행기를 닫는다.

        Args:
            wait: 실행 중인 세션이 끝날 때까지 기다릴지.
        """
        self._pool.shutdown(wait=wait, cancel_futures=not wait)

    def _run(self, context: ExecutionContext) -> None:
        """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음."""
        # 저장소 갱신은 모두 이 실행의 context로. 시간 초과 뒤 재접수된 새 세션은 건드리지 않음
        try:
            started = self.store.start(context)
            # 대기 중 시간 초과로 이미 실패한 세션
            if started is None:
                return
            self._publish(started)
            # 첫 실행은 이전 결과·답변이 비어 있음
            job_input = DiagnosisInput(source=started.source, previous=started.result, answers=started.answers)
            try:
                result = self._job(job_input, context, _Progress(self, context))
                if (result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED
                        and started.question_round >= MAX_QUESTION_ROUNDS):
                    result = _close_at_question_limit(result, context)
                # 질문 변환 실패도 진단 실패로. 질문 없이 답변 대기로 두면 BE에서 진행 중으로 남음
                questions = (
                    self._questions(result)
                    if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED
                    else None
                )
            except Exception:
                logger.exception(
                    "진단 실행 실패 (product_id=%s, run_id=%s)", context.product_id, context.run_id,
                )
                # 일시적 오류인지 알 수 없어 재시도 불가로 기록. 코드 오류를 BE가 계속 재요청하지 않게 함
                self._publish(self.store.fail(
                    context, error_code=AIResponseCode.PIPELINE_ERROR.value.code, retryable=False,
                ))
                return
            self._publish(self.store.finish(context, result, questions))
        finally:
            # 답변 대기로 끝나도 실행 자리 반납
            with self._lock:
                self._inflight -= 1
                self._dev_runs.discard(context.run_id)

    def _publish(self, session: DiagnosisSession | None) -> None:
        """바뀐 세션을 구독자에게 전달한다. 구독자 오류는 실행에 영향 없음."""
        if session is None:
            return
        for listener in self._listeners:
            try:
                listener(session)
            except Exception:
                logger.warning("세션 구독자 처리 실패 (product_id=%s)", session.context.product_id, exc_info=True)

    def _publish_tool(self, session: DiagnosisSession, tool_name: ToolName, status: ToolProgressStatus) -> None:
        """Tool 진행을 구독자에게 전달한다. 구독자 오류는 실행에 영향 없음."""
        for listener in self._tool_listeners:
            try:
                listener(session, tool_name, status)
            except Exception:
                logger.warning("Tool 진행 구독자 처리 실패 (product_id=%s, tool=%s)",
                               session.context.product_id, tool_name, exc_info=True)
