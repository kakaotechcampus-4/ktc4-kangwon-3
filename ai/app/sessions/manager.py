"""진단 세션의 접수·실행·조회·정리를 맡는 세션 관리자. 라우터·콜백·정리 루프는 이 관리자만 씀.

접수한 세션은 실행 상한 안에서 백그라운드로 실행. 에이전트 호출이 동기라 스레드 풀 사용.
실행할 진단 함수는 주입식 (파이프라인 러너 연결 전).
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from typing import assert_never
from uuid import uuid4

from ..config import (
    MAX_DEV_INFLIGHT_SESSIONS, MAX_INFLIGHT_SESSIONS, MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS,
)
from ..errors import AIResponseCode
from ..observability.context import ExecutionContext, PipelineStage, RunType
from ..schemas.agent import ExtractionInput
from ..schemas.base import utc_now
from ..schemas.schemas import ToolName
from ..schemas.session import DiagnosisSession
from .errors import QueueFullError, SessionConflictError
from .events import SessionEvent
from .job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, ToolProgressStatus
from .store import SessionStore
from .transitions import (
    STATUS_TRAITS, AskUser, Change, ChangeStage, Complete, Fail, InvalidTransitionError, ReportTool, Start,
    Transition, apply,
)

logger = logging.getLogger(__name__)

# 세션 이벤트마다 호출. 콜백 전송기 자리
SessionListener = Callable[[SessionEvent], None]


class _Progress:
    """세션 하나의 진행 알림. 자기 실행(run_id)의 세션에만 적용."""

    def __init__(self, manager: "SessionManager", context: ExecutionContext) -> None:
        self._manager = manager
        self._context = context

    def stage(self, stage: PipelineStage) -> None:
        self._manager._apply(self._context, ChangeStage(stage))

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        self._manager._apply(self._context, ReportTool(tool_name, status))


class SessionManager:
    """세션을 접수해 진단 함수를 백그라운드로 실행하고, 조회·정리를 맡는다."""

    def __init__(
        self,
        store: SessionStore,
        job: DiagnosisJob,
        *,
        max_running: int = MAX_RUNNING_SESSIONS,
        max_inflight: int = MAX_INFLIGHT_SESSIONS,
        max_dev_inflight: int = MAX_DEV_INFLIGHT_SESSIONS,
        max_duration: timedelta = timedelta(seconds=SESSION_MAX_DURATION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """세션 관리자를 만든다.

        Args:
            store: 세션 저장소.
            job: 실행할 진단 함수.
            max_running: 동시 실행 상한.
            max_inflight: 대기 + 실행 중 세션 상한.
            max_dev_inflight: 개발용 진단의 대기 + 실행 중 상한. 전체 상한에도 같이 셈.
            max_duration: 접수부터 결과까지 최대 시간.
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
        """
        self._store = store
        self._job = job
        self._pool = ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="diagnosis")
        self._max_inflight = max_inflight
        self._max_dev_inflight = max_dev_inflight
        self._max_duration = max_duration
        self._clock = clock
        self._listeners: list[SessionListener] = []
        # 접수 확인(진행 중 상품·상한)과 세션 추가를 묶는 잠금
        self._lock = Lock()
        self._inflight = 0
        # 실행 중인 개발용 진단의 run_id. 끝나면 개발용 자리도 반납
        self._dev_runs: set[str] = set()

    def subscribe(self, listener: SessionListener) -> None:
        """세션 이벤트(시작·단계 변경·Tool 진행·완료·답변 대기·실패)마다 부를 함수를 등록한다.

        Args:
            listener: 세션 이벤트를 받는 함수.
        """
        self._listeners.append(listener)

    def get(self, product_id: str) -> DiagnosisSession | None:
        """세션을 조회한다.

        Args:
            product_id: 세션 ID (상품 ID).

        Returns:
            DiagnosisSession | None: 세션. 없거나 정리됐으면 None.
        """
        return self._store.get(product_id)

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
            sessions = self._accept(diagnosis_id, [item.product_id for item in inputs], RunType.PRODUCTION)
            self._inflight += len(inputs)

        for item, session in zip(inputs, sessions):
            self._pool.submit(self._run, item, session.context)
        return sessions

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
            [session] = self._accept(None, [product_id], RunType.TEST)
            self._inflight += 1
            self._dev_runs.add(session.context.run_id)

        self._pool.submit(self._run, item, session.context)
        return session

    def expire_overdue(self) -> int:
        """접수부터 최대 시간을 넘긴 세션을 시간 초과 실패로 끝낸다.

        실행 중인 스레드는 멈출 수 없어서, 나중에 결과가 와도 전이표가 거절함.

        Returns:
            int: 실패로 바꾼 세션 수.
        """
        deadline = self._clock() - self._max_duration
        expired = 0
        for session in self._store.unfinished():
            if session.accepted_at > deadline:
                continue
            fail = Fail(AIResponseCode.TIMEOUT.value.code, retryable=True)
            if self._apply(session.context, fail) is not None:
                expired += 1
        return expired

    def purge(self) -> int:
        """보관 시간이 지난 종료 세션을 지운다. 답변 대기 세션은 남김.

        Returns:
            int: 지운 세션 수.
        """
        return self._store.purge()

    def shutdown(self, *, wait: bool = False) -> None:
        """새 실행을 받지 않고 관리자를 닫는다.

        Args:
            wait: 실행 중인 세션이 끝날 때까지 기다릴지.
        """
        self._pool.shutdown(wait=wait, cancel_futures=not wait)

    def _run(self, item: ExtractionInput, context: ExecutionContext) -> None:
        """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음."""
        # 세션 변경은 모두 이 실행의 context로. 시간 초과 뒤 재접수된 새 세션은 건드리지 않음
        try:
            # 대기 중 시간 초과로 이미 실패한 세션이면 실행하지 않음
            if self._apply(context, Start()) is None:
                return
            try:
                outcome = self._job(item, context, _Progress(self, context))
            except Exception:
                logger.exception(
                    "진단 실행 실패 (product_id=%s, run_id=%s)", context.product_id, context.run_id,
                )
                # 일시적 오류인지 알 수 없어 재시도 불가로 기록. 코드 오류를 BE가 계속 재요청하지 않게 함
                self._apply(context, Fail(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False))
                return
            match outcome:
                case JobDone(result=result):
                    self._apply(context, Complete(result))
                case JobNeedsInput(result=result):
                    self._apply(context, AskUser(result))
                case JobFailed(error_code=error_code, retryable=retryable):
                    self._apply(context, Fail(error_code, retryable))
                case _:
                    assert_never(outcome)
        finally:
            # 답변 대기로 끝나도 실행 자리 반납
            with self._lock:
                self._inflight -= 1
                self._dev_runs.discard(context.run_id)

    def _accept(self, diagnosis_id: str | None, product_ids: list[str], run_type: RunType) -> list[DiagnosisSession]:
        """상품들을 새 세션으로 저장소에 넣는다. self._lock 안에서 부름.

        하나라도 진행 중이면 아무것도 넣지 않고 전체를 거절함 (#263). 완료·실패한 상품은 새 세션으로 교체.
        진행 중이 아닌 상태에서 진행 중으로 가는 길은 접수뿐이라, 확인과 추가 사이에 다른 스레드가 끼어들 수 없음.

        Args:
            diagnosis_id: BE 진단서 ID. 개발용 진단은 None (콜백 대상 아님).
            product_ids: 접수할 상품 ID 목록.
            run_type: 실행 종류. 개발용 진단은 TEST.

        Returns:
            list[DiagnosisSession]: 접수된 세션. product_ids 순서와 같음.

        Raises:
            SessionConflictError: 진행 중인 상품이 하나라도 있는 경우.
        """
        conflicts = [
            product_id for product_id in product_ids
            if (session := self._store.get(product_id)) and STATUS_TRAITS[session.status].blocks_new_accept
        ]
        if conflicts:
            raise SessionConflictError(conflicts)

        now = self._clock()
        sessions = [
            DiagnosisSession(
                context=ExecutionContext.start(product_id=product_id, run_type=run_type, diagnosis_id=diagnosis_id),
                accepted_at=now, updated_at=now,
            )
            for product_id in product_ids
        ]
        self._store.add(sessions)
        return sessions

    def _apply(self, context: ExecutionContext, change: Change) -> Transition | None:
        """이 실행의 세션에 전이표대로 일을 적용하고 이벤트를 구독자에게 알린다.

        Args:
            context: 이 실행의 컨텍스트.
            change: 일어난 일.

        Returns:
            Transition | None: 전이 결과. 재접수로 다른 실행이 됐거나, 지금 상태에서 할 수 없는 일
                (시간 초과 뒤 늦게 온 결과 등)이면 None.
        """
        try:
            transition = self._store.replace(context, lambda session: apply(session, change, now=self._clock()))
        except InvalidTransitionError as e:
            logger.warning("세션 상태와 맞지 않는 변경 무시 (product_id=%s, run_id=%s): %s",
                           context.product_id, context.run_id, e)
            return None
        if transition is None:
            return None
        for event in transition.events:
            self._publish(event)
        return transition

    def _publish(self, event: SessionEvent) -> None:
        """세션 이벤트를 구독자에게 전달한다. 구독자 오류는 실행에 영향 없음."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.warning("세션 구독자 처리 실패 (product_id=%s, event=%s)",
                               event.session.context.product_id, type(event).__name__, exc_info=True)
