"""접수한 진단 세션을 실행 상한 안에서 백그라운드로 실행.

에이전트 호출이 동기라 스레드 풀 사용. 실행할 진단 함수는 주입식 (파이프라인 러너 연결 전).
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from typing import Protocol

from ..config import MAX_INFLIGHT_SESSIONS, MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS
from ..observability.context import ExecutionContext, PipelineStage
from ..schemas.agent import ExtractionInput
from ..schemas.base import utc_now
from ..schemas.schemas import FinalAssessment
from ..schemas.session import DiagnosisSession
from .store import SessionStore

logger = logging.getLogger(__name__)

# 실패 코드. #171 §6 응답 코드 체계가 BE와 합의되면 교체
ERROR_PIPELINE = "AI_PIPELINE_ERROR"
ERROR_TIMEOUT = "AI_TIMEOUT"


class ProgressReporter(Protocol):
    """진단 함수가 단계가 바뀔 때 부르는 진행 알림."""

    def stage(self, stage: PipelineStage) -> None: ...


# 상품 입력, 실행 컨텍스트, 진행 알림을 받아 최종 결과를 돌려주는 진단 함수
DiagnosisJob = Callable[[ExtractionInput, ExecutionContext, ProgressReporter], FinalAssessment]
# 세션 상태가 바뀔 때마다 호출. 이후 콜백 전송기 자리
SessionListener = Callable[[DiagnosisSession], None]


class QueueFullError(RuntimeError):
    """대기 + 실행 중 세션이 상한을 넘어 접수를 거절한 경우."""


class _Progress:
    """세션 하나의 진행 알림. 저장소 갱신 후 구독자에게 전달."""

    def __init__(self, executor: "SessionExecutor", product_id: str) -> None:
        self._executor = executor
        self._product_id = product_id

    def stage(self, stage: PipelineStage) -> None:
        self._executor._publish(self._executor.store.update_stage(self._product_id, stage))


class SessionExecutor:
    """세션을 접수해 진단 함수를 백그라운드로 실행한다."""

    def __init__(
        self,
        store: SessionStore,
        job: DiagnosisJob,
        *,
        max_running: int = MAX_RUNNING_SESSIONS,
        max_inflight: int = MAX_INFLIGHT_SESSIONS,
        max_duration: timedelta = timedelta(seconds=SESSION_MAX_DURATION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """실행기를 만든다.

        Args:
            store: 세션 저장소.
            job: 실행할 진단 함수.
            max_running: 동시 실행 상한.
            max_inflight: 대기 + 실행 중 세션 상한.
            max_duration: 접수부터 결과까지 최대 시간.
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
        """
        self.store = store
        self._job = job
        self._pool = ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="diagnosis")
        self._max_inflight = max_inflight
        self._max_duration = max_duration
        self._clock = clock
        self._listeners: list[SessionListener] = []
        self._lock = Lock()
        self._inflight = 0

    def subscribe(self, listener: SessionListener) -> None:
        """세션 상태가 바뀔 때마다 부를 함수를 등록한다.

        Args:
            listener: 바뀐 세션을 받는 함수.
        """
        self._listeners.append(listener)

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
            sessions = self.store.accept(diagnosis_id, [item.product_id for item in inputs])
            self._inflight += len(inputs)

        for item, session in zip(inputs, sessions):
            self._pool.submit(self._run, item, session.context)
        return sessions

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
            failed = self.store.fail(session.context.product_id, error_code=ERROR_TIMEOUT, retryable=True)
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

    def _run(self, item: ExtractionInput, context: ExecutionContext) -> None:
        """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음."""
        product_id = context.product_id
        try:
            started = self.store.start(product_id)
            # 대기 중 시간 초과로 이미 실패한 세션
            if started is None:
                return
            self._publish(started)
            try:
                result = self._job(item, context, _Progress(self, product_id))
            except Exception:
                logger.exception("진단 실행 실패 (product_id=%s, run_id=%s)", product_id, context.run_id)
                self._publish(self.store.fail(product_id, error_code=ERROR_PIPELINE, retryable=True))
                return
            self._publish(self.store.finish(product_id, result))
        finally:
            # 답변 대기로 끝나도 실행 자리 반납
            with self._lock:
                self._inflight -= 1

    def _publish(self, session: DiagnosisSession | None) -> None:
        """바뀐 세션을 구독자에게 전달한다. 구독자 오류는 실행에 영향 없음."""
        if session is None:
            return
        for listener in self._listeners:
            try:
                listener(session)
            except Exception:
                logger.warning("세션 구독자 처리 실패 (product_id=%s)", session.context.product_id, exc_info=True)
