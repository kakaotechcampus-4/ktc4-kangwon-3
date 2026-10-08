"""진단 세션을 상품 단위로 메모리에 보관하는 저장소.

AI 재시작 시 세션은 사라짐. 실행기·라우터 등 여러 스레드가 함께 쓰므로 모든 변경은 잠금 안에서 처리.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from ..config import SESSION_RETENTION_SECONDS
from ..observability.context import ExecutionContext, PipelineStage, RunType
from ..schemas.base import utc_now
from ..schemas.schemas import ExecutionEndReason, FinalAssessment
from ..schemas.session import DiagnosisSession, SessionStatus

# 진행 중으로 보는 상태. 같은 상품의 새 접수를 막음
ACTIVE_STATUSES = frozenset({SessionStatus.ACCEPTED, SessionStatus.RUNNING, SessionStatus.AWAITING_INPUT})
# 보관 시간이 지나면 지우는 상태
FINISHED_STATUSES = frozenset({SessionStatus.COMPLETED, SessionStatus.FAILED})


class SessionConflictError(RuntimeError):
    """진행 중인 상품이 요청에 섞여 있어 접수를 거절한 경우.

    Attributes:
        product_ids: 이미 진행 중인 상품 ID 목록.
    """

    def __init__(self, product_ids: list[str]) -> None:
        super().__init__(f"이미 진행 중인 상품이 있습니다: {', '.join(product_ids)}")
        self.product_ids = product_ids


class SessionStore:
    """상품 ID를 세션 ID로 쓰는 진단 세션 저장소."""

    def __init__(
        self,
        *,
        retention: timedelta = timedelta(seconds=SESSION_RETENTION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """저장소를 만든다.

        Args:
            retention: 종료된 세션 보관 시간.
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
        """
        self._sessions: dict[str, DiagnosisSession] = {}
        self._lock = Lock()
        self._retention = retention
        self._clock = clock

    def accept(self, diagnosis_id: str, product_ids: list[str]) -> list[DiagnosisSession]:
        """진단서 한 건의 상품들을 세션으로 접수한다.

        하나라도 진행 중이면 아무것도 접수하지 않고 전체를 거절함 (#263).
        완료·실패한 상품은 새 세션으로 교체.

        Args:
            diagnosis_id: BE 진단서 ID.
            product_ids: 접수할 상품 ID 목록.

        Returns:
            list[DiagnosisSession]: 접수된 세션. product_ids 순서와 같음.

        Raises:
            SessionConflictError: 진행 중인 상품이 하나라도 있는 경우.
        """
        with self._lock:
            conflicts = [
                product_id for product_id in product_ids
                if (session := self._sessions.get(product_id)) and session.status in ACTIVE_STATUSES
            ]
            if conflicts:
                raise SessionConflictError(conflicts)

            now = self._clock()
            accepted = []
            for product_id in product_ids:
                context = ExecutionContext.start(
                    product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id=diagnosis_id,
                )
                session = DiagnosisSession(context=context, accepted_at=now, updated_at=now)
                self._sessions[product_id] = session
                accepted.append(session)
            return accepted

    def get(self, product_id: str) -> DiagnosisSession | None:
        """세션을 조회한다.

        Args:
            product_id: 세션 ID (상품 ID).

        Returns:
            DiagnosisSession | None: 세션. 없거나 정리됐으면 None.
        """
        with self._lock:
            return self._sessions.get(product_id)

    def start(self, product_id: str) -> DiagnosisSession | None:
        """접수된 세션을 실행 중으로 바꾼다.

        Args:
            product_id: 세션 ID.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 접수 상태가 아니면(이미 시간 초과로 실패 등) None.
        """
        return self._transition(product_id, {SessionStatus.ACCEPTED}, status=SessionStatus.RUNNING)

    def update_stage(self, product_id: str, stage: PipelineStage) -> DiagnosisSession | None:
        """실행 중인 세션의 현재 단계를 기록한다.

        Args:
            product_id: 세션 ID.
            stage: 새 단계.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 실행 중이 아니면 None.
        """
        return self._transition(
            product_id, {SessionStatus.RUNNING}, stage=stage, stage_started_at=self._clock(),
        )

    def finish(self, product_id: str, result: FinalAssessment) -> DiagnosisSession | None:
        """실행 결과를 기록한다.

        종료 사유가 user_input_required면 답변 대기, 그 외는 완료로 둠.

        Args:
            product_id: 세션 ID.
            result: 파이프라인 최종 결과.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 실행 중이 아니면(시간 초과로 이미 실패 등) None. 늦게 끝난 결과 무시용.
        """
        status = (
            SessionStatus.AWAITING_INPUT
            if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED
            else SessionStatus.COMPLETED
        )
        return self._transition(
            product_id, {SessionStatus.RUNNING},
            status=status, termination_reason=result.termination_reason, result=result,
        )

    def fail(self, product_id: str, *, error_code: str, retryable: bool) -> DiagnosisSession | None:
        """접수·실행 중인 세션을 실패로 끝낸다.

        종료 사유로 바꾸지 않고 오류 코드로만 기록함 (#171 §7.1.1).

        Args:
            product_id: 세션 ID.
            error_code: 실패 코드.
            retryable: 같은 요청을 다시 보내 복구 가능한지.

        Returns:
            DiagnosisSession | None: 바뀐 세션. 이미 끝났으면 None.
        """
        return self._transition(
            product_id, {SessionStatus.ACCEPTED, SessionStatus.RUNNING},
            status=SessionStatus.FAILED, error_code=error_code, retryable=retryable,
        )

    def purge(self) -> int:
        """보관 시간이 지난 종료 세션을 지운다. 답변 대기 세션은 남김.

        Returns:
            int: 지운 세션 수.
        """
        with self._lock:
            deadline = self._clock() - self._retention
            expired = [
                product_id for product_id, session in self._sessions.items()
                if session.status in FINISHED_STATUSES and session.updated_at <= deadline
            ]
            for product_id in expired:
                del self._sessions[product_id]
            return len(expired)

    def _transition(
        self, product_id: str, allowed: set[SessionStatus], **changes: Any,
    ) -> DiagnosisSession | None:
        """허용된 상태일 때만 세션을 바꾼다. 바꾼 세션은 새 객체로 교체."""
        with self._lock:
            session = self._sessions.get(product_id)
            if session is None or session.status not in allowed:
                return None
            # 검증(UTC 정규화 등)을 다시 거치도록 model_copy 대신 새로 만듦
            updated = DiagnosisSession.model_validate(
                {**dict(session), **changes, "updated_at": self._clock()},
            )
            self._sessions[product_id] = updated
            return updated
