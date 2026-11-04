"""진단 세션의 접수·실행·조회·정리를 맡는 세션 관리자. 라우터·콜백·정리 루프는 이 관리자만 씀.

자리 계산(capacity)·상태 변경(updater)·진단 실행(runner)을 조립함.
접수한 세션은 실행 상한 안에서 백그라운드로 실행. 에이전트 호출이 동기라 스레드 풀 사용.
실행할 진단 함수는 주입식 (main.py가 실행 종류별로 골라 넣음).
"""

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from datetime import datetime, timedelta
from threading import Lock
from time import perf_counter
from uuid import uuid4

from ...config import (
    MAX_DEV_INFLIGHT_SESSIONS, MAX_INFLIGHT_SESSIONS, MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS,
)
from ...domain.errors import AIResponseCode
from ...domain.context import ExecutionContext, RunType
from ...observability.logs import log_fields, run_log_context
from ...schemas.agent import ExtractionInput
from ...schemas.base import utc_now
from ...schemas.session import DiagnosisSession, SessionAnswer, SessionStatus
from ..errors import (
    QueueFullError, ResumeConflictError, SessionConflictError, SessionError, SessionNotFoundError,
    UnansweredQuestionError, UnknownQuestionKeyError,
)
from ..job import DiagnosisJob
from ..store import SessionStore
from ..transitions import STATUS_TRAITS, TRANSITIONS, Fail, Resume, Transition, apply
from .capacity import SessionCapacity
from .runner import run_session
from .snapshot import RejectReason, SessionSnapshot
from .updater import SessionListener, SessionUpdater

logger = logging.getLogger(__name__)


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
        self._capacity = SessionCapacity(max_inflight=max_inflight, max_dev_inflight=max_dev_inflight)
        self._updater = SessionUpdater(store, clock)
        self._max_running = max_running
        self._max_inflight = max_inflight
        self._max_dev_inflight = max_dev_inflight
        self._max_duration = max_duration
        self._clock = clock
        # 접수·재진단 확인(상한·진행 중 상품·답변)부터 세션 교체·자리 차지·접수 집계까지 묶는 잠금
        self._lock = Lock()
        self._accepted: dict[RunType, int] = dict.fromkeys(RunType, 0)
        self._rejected: dict[RejectReason, int] = {"queue_full": 0, "conflict": 0}
        self._awaiting_replaced = 0
        # 시작 전·실행 중 세션의 실행 예약. 종료 때 실행 중인 것만 기다리려고 둠
        self._futures: set[Future] = set()
        self._futures_lock = Lock()

    def subscribe(self, listener: SessionListener) -> None:
        """세션 이벤트(시작·단계 변경·Tool 진행·완료·답변 대기·실패)마다 부를 함수를 등록한다.

        Args:
            listener: 세션 이벤트를 받는 함수.
        """
        self._updater.subscribe(listener)

    def get(self, product_id: str) -> DiagnosisSession | None:
        """세션을 조회한다.

        Args:
            product_id: 세션 ID (상품 ID).

        Returns:
            DiagnosisSession | None: 세션. 없거나 정리됐으면 None.
        """
        return self._store.get(product_id)

    def snapshot(self) -> SessionSnapshot:
        """지금 현황을 읽는다. 상태별 수·자리·상한·누적 접수/거절/답변 대기 교체.

        Returns:
            SessionSnapshot: 읽은 순간의 현황. 항목마다 따로 읽어 서로 잠깐 어긋날 수 있음.
        """
        with self._lock:
            accepted, rejected, awaiting_replaced = dict(self._accepted), dict(self._rejected), self._awaiting_replaced
        return SessionSnapshot(
            status_counts=self._store.count_by_status(),
            inflight=self._capacity.inflight,
            dev_inflight=self._capacity.dev_inflight,
            max_running=self._max_running,
            max_inflight=self._max_inflight,
            max_dev_inflight=self._max_dev_inflight,
            accepted=accepted,
            rejected=rejected,
            awaiting_replaced=awaiting_replaced,
        )

    def submit(
        self, diagnosis_id: str, inputs: list[ExtractionInput], run_type: RunType = RunType.PRODUCTION,
    ) -> list[DiagnosisSession]:
        """상품들을 세션으로 접수하고 백그라운드 실행을 예약한다.

        Args:
            diagnosis_id: BE 진단서 ID.
            inputs: 상품별 입력. product_id가 세션 ID.
            run_type: 실행 종류. 운영 진단은 PRODUCTION, BE 연동 더미는 DUMMY. 둘 다 전체 상한만 봄.

        Returns:
            list[DiagnosisSession]: 접수된 세션.

        Raises:
            QueueFullError: 대기 + 실행 중 세션이 상한을 넘는 경우.
            SessionConflictError: 실행 중인 상품이 섞인 경우.
        """
        sessions = self._accept(diagnosis_id, inputs, run_type)
        for session in sessions:
            self._schedule(session.context)
        return sessions

    def resume(
        self,
        *,
        diagnosis_id: str,
        product_id: str,
        run_id: str,
        question_round: int,
        answers: dict[str, str],
        run_type: RunType = RunType.PRODUCTION,
    ) -> DiagnosisSession:
        """답변 대기 세션을 답변과 함께 재접수하고 새 실행을 예약한다. 접수와 같은 대기열·상한 사용.

        Args:
            diagnosis_id: BE 진단서 ID. 세션과 같아야 함.
            product_id: 세션 ID (상품 ID).
            run_id: 질문으로 끝난 실행 ID. 지금 세션의 실행과 같아야 함.
            question_round: 답하는 질문 회차. 지금 기다리는 회차와 같아야 함.
            answers: 질문 키 → 답변. 이번 회차 질문에 모두 답해야 함.
            run_type: 재진단 경로의 실행 종류. 세션의 실행 종류와 같아야 함.

        Returns:
            DiagnosisSession: 재접수된 세션. context.run_id가 새 실행 ID.

        Raises:
            QueueFullError: 대기 + 실행 중 세션이 상한을 넘는 경우.
            SessionNotFoundError: 세션이 없거나 실행 종류가 다른 경우.
            ResumeConflictError: 답변 대기가 아니거나 실행·회차·진단서가 다른 경우.
            UnknownQuestionKeyError: 이번 회차에 묻지 않은 질문 키가 있는 경우.
            UnansweredQuestionError: 이번 회차 질문 중 답하지 않은 질문이 있는 경우.
        """

        def resume(session: DiagnosisSession) -> Transition:
            if (session.status, Resume) not in TRANSITIONS:
                raise ResumeConflictError(f"답변 대기 상태가 아닙니다: {product_id} ({session.status})")
            expected = (session.context.diagnosis_id, session.context.run_id, session.question_round)
            if (diagnosis_id, run_id, question_round) != expected:
                raise ResumeConflictError(f"기다리는 질문과 다른 답변입니다: {product_id}")
            _check_answers(session, answers)
            context = ExecutionContext.start(
                product_id=product_id, run_type=session.context.run_type, diagnosis_id=diagnosis_id,
            )
            new_answers = [
                SessionAnswer(question_round=question_round, question_key=key, answer_text=text)
                for key, text in answers.items()
            ]
            return apply(session, Resume(context, new_answers), now=self._clock())

        try:
            with self._lock:
                try:
                    self._capacity.check(1, dev=False)
                except QueueFullError:
                    self._rejected["queue_full"] += 1
                    raise
                session = self._store.get(product_id)
                # 다른 경로(운영·더미)로 접수된 세션은 없음으로 봄
                if session is not None and session.context.run_type is not run_type:
                    session = None
                # 조회 뒤 정리로 사라져도 없음으로 봄. 같은 상품의 접수·재진단은 이 잠금 안에서만 일어남
                transition = self._updater.replace(session.context, resume) if session is not None else None
                if transition is None:
                    raise SessionNotFoundError(f"세션이 없습니다: {product_id}")
                resumed = transition.session
                self._capacity.take([resumed.context.run_id], dev=resumed.context.run_type is RunType.TEST)
                self._accepted[resumed.context.run_type] += 1
        except SessionError as exc:
            # 라우터가 4xx 응답으로 바꿔 앱 로그가 없으면 거절 이유가 안 보임. 잠금 밖에서 남김
            fields = {"diagnosis_id": diagnosis_id, "product_id": product_id, "run_id": run_id,
                      "run_type": run_type.value}
            with log_fields(fields):
                logger.warning("재진단 접수 거절: %s (질문 회차 %d, 답변 %d개)", exc, question_round, len(answers))
            raise

        with run_log_context(resumed.context):
            logger.info("재진단 접수 (질문 회차 %d, 답변 %d개)", question_round, len(answers))
        self._schedule(resumed.context)
        return resumed

    def restore(self, sessions: list[DiagnosisSession]) -> None:
        """재시작 전에 보관해 둔 세션을 되살린다 (#565). 서버 기동 때 접수를 받기 전에 한 번 부름.

        대기 세션은 자리를 잡고 같은 실행 ID로 다시 실행. 이 실행으로 보낸 콜백이 없어 BE는 차이를 모름.
        접수 시각은 그대로라 오래 내려가 있었으면 실행 전에 시간 초과로 끝남.
        답변 대기 세션은 저장소에만 넣어 답이 오면 재진단. 그 밖의 상태는 되살리지 않음.

        Args:
            sessions: 보관소에서 읽은 세션.
        """
        queued = sorted((s for s in sessions if s.status is SessionStatus.ACCEPTED), key=lambda s: s.accepted_at)
        awaiting = [s for s in sessions if s.status is SessionStatus.AWAITING_INPUT]
        skipped = len(sessions) - len(queued) - len(awaiting)
        with self._lock:
            self._store.add([*awaiting, *queued])
            # 상한 확인 없이 차지함. 보관할 때도 상한 안이었음
            self._capacity.take([session.context.run_id for session in queued], dev=False)
        for session in awaiting:
            with run_log_context(session.context):
                logger.info("재시작 전 답변 대기 세션 복원 (질문 회차 %d)", session.question_round)
        for session in queued:
            with run_log_context(session.context):
                logger.info("재시작 전 대기 세션 복원, 다시 실행 (답변 %d개)", len(session.answers))
            self._schedule(session.context)
        if sessions:
            logger.info("진단 세션 복원: 대기 %d개, 답변 대기 %d개, 되살리지 않음 %d개",
                        len(queued), len(awaiting), skipped)

    def submit_dev(self, items: list[ExtractionInput]) -> list[DiagnosisSession]:
        """개발용 진단 상품들을 접수한다. 진단서 없이 접수해 콜백은 나가지 않음.

        상품 ID는 운영 상품과 겹치지 않게 dev- 접두어로 새로 발급하고, 입력의 product_id는 쓰지 않음.
        상한을 넘으면 전체를 거절함.

        Args:
            items: 상품별 입력.

        Returns:
            list[DiagnosisSession]: 접수된 세션. items 순서와 같고 상품 ID는 발급한 dev- ID.

        Raises:
            QueueFullError: 개발용 상한 또는 전체 상한을 넘는 경우.
        """
        items = [item.model_copy(update={"product_id": f"dev-{uuid4()}"}) for item in items]
        sessions = self._accept(None, items, RunType.TEST)
        for session in sessions:
            self._schedule(session.context)
        return sessions

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
            if self._updater.apply(session.context, fail) is not None:
                expired += 1
        return expired

    def purge(self) -> int:
        """보관 시간이 지난 종료·답변 대기 세션을 지운다.

        Returns:
            int: 지운 세션 수.
        """
        return self._store.purge()

    def shutdown(self, *, wait: bool = False) -> None:
        """새 실행을 받지 않고 관리자를 닫는다. 기다리지 않으면 버리는 세션을 경고로 남김.

        Args:
            wait: 실행 중인 세션이 끝날 때까지 기다릴지.
        """
        if not wait:
            _log_abandoned(self._store.unfinished(), self._store.count_by_status().get(SessionStatus.AWAITING_INPUT, 0))
        self._pool.shutdown(wait=wait, cancel_futures=not wait)

    def drain(self, timeout: float) -> None:
        """서버 종료 때 대기열은 취소하고 실행 중인 세션만 상한 시간까지 기다린 뒤 관리자를 닫는다.

        기다리는 동안 끝난 세션은 평소처럼 이벤트(결과 콜백)가 나감.
        남은 세션이 모두 최대 시간을 넘기는 시각이 상한보다 이르면 그때까지만 기다리고,
        최대 시간을 넘긴 세션은 시간 초과 실패로 끝냄 (정리 루프 주기를 기다리지 않음).
        취소한 대기 세션, 상한을 넘긴 실행 중 세션, 답변 대기 세션은 경고로 남기고 버림.

        Args:
            timeout: 실행 중인 세션을 기다릴 최대 시간(초).
        """
        self._pool.shutdown(wait=False, cancel_futures=True)
        with self._futures_lock:
            running = [future for future in self._futures if not future.cancelled()]
        if running:
            # 마감이 지난 세션은 결과가 나와도 버려져 더 기다리지 않음
            wait_seconds = min(timeout, self._seconds_until_all_overdue())
            started_at = perf_counter()
            logger.info("서버 종료: 실행 중 진단 %d개를 최대 %.0f초 기다림", len(running), wait_seconds)
            _, left = wait_futures(running, timeout=wait_seconds)
            logger.info("서버 종료: 실행 중 진단 %d개 끝남, %d개 남음 (%.1f초)",
                        len(running) - len(left), len(left), perf_counter() - started_at)
        self.expire_overdue()
        _log_abandoned(self._store.unfinished(), self._store.count_by_status().get(SessionStatus.AWAITING_INPUT, 0))

    def _seconds_until_all_overdue(self) -> float:
        """끝나지 않은 세션이 모두 최대 시간을 넘길 때까지 남은 시간.

        Returns:
            float: 남은 시간(초). 끝나지 않은 세션이 없거나 모두 넘겼으면 0.
        """
        now = self._clock()
        remaining = [
            (session.accepted_at + self._max_duration - now).total_seconds() for session in self._store.unfinished()
        ]
        return max([0.0, *remaining])

    def _schedule(self, context: ExecutionContext) -> None:
        """세션 실행을 스레드 풀에 예약하고, 끝나면 예약 목록에서 뺀다.

        Args:
            context: 실행할 세션의 실행 정보.
        """
        future = self._pool.submit(self._run, context)
        with self._futures_lock:
            self._futures.add(future)
        future.add_done_callback(self._forget)

    def _forget(self, future: Future) -> None:
        """끝나거나 취소된 실행 예약을 목록에서 뺀다.

        Args:
            future: 끝난 실행 예약.
        """
        with self._futures_lock:
            self._futures.discard(future)

    def _run(self, context: ExecutionContext) -> None:
        """스레드 풀에서 세션 하나를 실행하고 자리를 반납한다."""
        try:
            run_session(self._job, context, self._updater)
        finally:
            # 답변 대기로 끝나도 실행 자리 반납
            self._capacity.release(context.run_id)

    def _accept(
        self, diagnosis_id: str | None, inputs: list[ExtractionInput], run_type: RunType,
    ) -> list[DiagnosisSession]:
        """자리와 실행 중 상품을 확인하고 새 세션으로 저장소에 넣어 자리를 차지한다.

        확인부터 자리 차지·집계까지 잠금 하나로 묶음. 상한을 넘거나 하나라도 실행 중이면
        아무것도 넣지 않고 전체를 거절함 (#263). 완료·실패·답변 대기 상품은 새 세션으로 교체.
        답변 대기 세션을 버리면 그 질문 회차의 재진단은 더 받지 않음 (#451).
        실행 중이 아닌 상태에서 실행 중으로 가는 길은 접수와 재진단뿐이고 둘 다 같은 잠금을 써서,
        확인과 추가 사이에 다른 스레드가 끼어들 수 없음.

        Args:
            diagnosis_id: BE 진단서 ID. 개발용 진단은 None (콜백 대상 아님).
            inputs: 접수할 상품별 입력. product_id가 세션 ID. 재진단용으로 세션에 보관.
            run_type: 실행 종류. 개발용 진단은 TEST이고 개발용 상한을 같이 봄.

        Returns:
            list[DiagnosisSession]: 접수된 세션. inputs 순서와 같음.

        Raises:
            QueueFullError: 개발용 상한 또는 전체 상한을 넘는 경우.
            SessionConflictError: 실행 중인 상품이 하나라도 있는 경우.
        """
        dev = run_type is RunType.TEST
        with self._lock:
            try:
                self._capacity.check(len(inputs), dev=dev)
                conflicts = [
                    item.product_id for item in inputs
                    if (session := self._store.get(item.product_id)) and STATUS_TRAITS[session.status].blocks_new_accept
                ]
                if conflicts:
                    raise SessionConflictError(conflicts)
            except QueueFullError:
                self._rejected["queue_full"] += 1
                _log_rejected(diagnosis_id, run_type, len(inputs), "대기열 가득 참")
                raise
            except SessionConflictError as exc:
                self._rejected["conflict"] += 1
                _log_rejected(diagnosis_id, run_type, len(inputs), f"진행 중인 상품 {', '.join(exc.product_ids)}")
                raise

            for item in inputs:
                replaced = self._store.get(item.product_id)
                if replaced is not None and replaced.status is SessionStatus.AWAITING_INPUT:
                    logger.info("답변 대기 세션을 버리고 새로 접수 (product_id=%s, run_id=%s, question_round=%d)",
                                item.product_id, replaced.context.run_id, replaced.question_round)
                    self._awaiting_replaced += 1

            now = self._clock()
            sessions = [
                DiagnosisSession(
                    context=ExecutionContext.start(
                        product_id=item.product_id, run_type=run_type, diagnosis_id=diagnosis_id,
                    ),
                    source=item, accepted_at=now, updated_at=now,
                )
                for item in inputs
            ]
            self._store.add(sessions)
            self._capacity.take([session.context.run_id for session in sessions], dev=dev)
            self._accepted[run_type] += len(sessions)
        for session in sessions:
            # 입력 모양만. 글·URL 본문은 남기지 않음
            source = session.source
            with run_log_context(session.context):
                logger.info("진단 접수 (글 %d개 %d자, 이미지 %d장, URL %s)", len(source.text_blocks),
                            sum(len(block) for block in source.text_blocks), len(source.image_urls),
                            "있음" if source.source_url else "없음")
        return sessions


def _log_rejected(diagnosis_id: str | None, run_type: RunType, count: int, reason: str) -> None:
    """접수 거절 한 줄. 세션을 만들기 전이라 진단서 ID·실행 종류만 붙임.

    Args:
        diagnosis_id: BE 진단서 ID. 개발용 진단은 None.
        run_type: 실행 종류.
        count: 요청한 상품 수.
        reason: 거절 이유.
    """
    with log_fields({"diagnosis_id": diagnosis_id, "run_type": run_type.value}):
        logger.warning("진단 접수 거절: %s (상품 %d개)", reason, count)


def _log_abandoned(unfinished: list[DiagnosisSession], awaiting: int) -> None:
    """서버 종료로 버리는 세션 한 줄 (#497). 버릴 세션이 없으면 남기지 않음.

    대기 중은 취소되고, 실행 중(drain이면 상한 시간을 넘긴 것만)은 프로세스가 끝나며 함께 끊김
    (uvicorn이 종료 신호를 다시 발생시킴).
    둘 다 결과 콜백이 나가지 않음. 답변 대기 세션은 메모리에만 있어 재시작 뒤 재진단할 수 없음.

    Args:
        unfinished: 접수·실행 중 세션.
        awaiting: 답변 대기 세션 수.
    """
    running = [s.context.product_id for s in unfinished if s.status is SessionStatus.RUNNING]
    queued = [s.context.product_id for s in unfinished if s.status is not SessionStatus.RUNNING]
    # 0개인 항목은 뺌
    parts, notes = [], []
    if running:
        parts.append(f"실행 중 {len(running)}개({', '.join(running)})")
    if queued:
        parts.append(f"대기 중 {len(queued)}개({', '.join(queued)})")
    if running or queued:
        notes.append("결과 콜백 없음")
    if awaiting:
        parts.append(f"답변 대기 {awaiting}개")
        notes.append("재시작 뒤 재진단 불가")
    if parts:
        logger.warning("서버 종료로 진단을 버림: %s (%s)", ", ".join(parts), ", ".join(notes))


def _check_answers(session: DiagnosisSession, answers: dict[str, str]) -> None:
    """답변이 이번 회차 질문과 꼭 맞는지 확인한다. 2회차는 새 키만 물어서 빠진 질문은 다시 물을 수 없음."""
    asked = {question.question_key for question in session.questions}
    unknown = [key for key in answers if key not in asked]
    if unknown:
        raise UnknownQuestionKeyError(unknown)
    # BE 답변 제출도 전부 답해야 받음
    unanswered = [question.question_key for question in session.questions if question.question_key not in answers]
    if unanswered:
        raise UnansweredQuestionError(unanswered)
