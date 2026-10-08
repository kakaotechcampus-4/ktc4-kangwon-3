"""진단 세션 실행기의 실행 상한·대기열·실패·시간 초과·진행 알림을 확인한다."""

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import PipelineStage
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.schemas.session import SessionStatus
from app.sessions.executor import ERROR_PIPELINE, ERROR_TIMEOUT, QueueFullError, SessionExecutor
from app.sessions.store import SessionConflictError, SessionStore

START = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class _GatedJob:
    """release() 전까지 상품별로 붙잡아 두는 진단 함수."""

    def __init__(self, result_for=build_dummy_assessment, raise_error: bool = False) -> None:
        self.started: list[str] = []
        self.gates: dict[str, threading.Event] = {}
        self._result_for = result_for
        self._raise_error = raise_error
        self._lock = threading.Lock()

    def __call__(self, item, context, progress):
        gate = threading.Event()
        with self._lock:
            self.gates[item.product_id] = gate
            self.started.append(item.product_id)
        progress.stage(PipelineStage.EXTRACTION)
        gate.wait(timeout=5)
        if self._raise_error:
            raise RuntimeError("파이프라인 오류")
        return self._result_for(item.product_id)

    def release(self, product_id: str) -> None:
        _wait_until(lambda: product_id in self.gates)
        self.gates[product_id].set()


def _wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("조건을 기다리다 시간 초과")
        time.sleep(0.01)


def _inputs(*product_ids: str) -> list[ExtractionInput]:
    return [ExtractionInput(product_id=pid, text_blocks=["상품 설명"]) for pid in product_ids]


def _status(store: SessionStore, product_id: str) -> SessionStatus | None:
    session = store.get(product_id)
    return session.status if session else None


@pytest.fixture
def executors():
    created = []
    yield created
    for executor in created:
        executor.shutdown(wait=False)


def _executor(executors, job, **kwargs) -> SessionExecutor:
    clock = kwargs.pop("clock", _Clock())
    executor = SessionExecutor(SessionStore(clock=clock), job, clock=clock, **kwargs)
    executors.append(executor)
    return executor


def test_결과가_나오면_완료로_기록하고_상태_변화를_구독자에게_알린다(executors):
    job = _GatedJob()
    executor = _executor(executors, job)
    seen = []
    executor.subscribe(lambda s: seen.append((s.status, s.stage)))

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)

    assert seen == [
        (SessionStatus.RUNNING, None),
        (SessionStatus.RUNNING, PipelineStage.EXTRACTION),
        (SessionStatus.COMPLETED, PipelineStage.EXTRACTION),
    ]


def test_진단_함수_예외는_실패로_기록한다(executors):
    job = _GatedJob(raise_error=True)
    executor = _executor(executors, job)

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.FAILED)

    session = executor.store.get("p-1")
    assert (session.error_code, session.retryable) == (ERROR_PIPELINE, True)


def test_실행_상한을_넘는_세션은_자리가_날_때까지_기다린다(executors):
    job = _GatedJob()
    executor = _executor(executors, job, max_running=2)

    executor.submit("d-1", _inputs("p-1", "p-2", "p-3"))
    _wait_until(lambda: len(job.started) == 2)
    time.sleep(0.05)

    assert _status(executor.store, "p-3") is SessionStatus.ACCEPTED

    job.release(job.started[0])
    _wait_until(lambda: len(job.started) == 3)
    assert _status(executor.store, "p-3") is SessionStatus.RUNNING


def test_대기열이_가득_차면_접수를_거절하고_세션을_만들지_않는다(executors):
    job = _GatedJob()
    executor = _executor(executors, job, max_running=1, max_inflight=2)
    executor.submit("d-1", _inputs("p-1", "p-2"))

    with pytest.raises(QueueFullError):
        executor.submit("d-2", _inputs("p-3"))

    assert executor.store.get("p-3") is None


def test_진행_중인_상품이_섞이면_접수하지_않고_대기열도_차지하지_않는다(executors):
    job = _GatedJob()
    executor = _executor(executors, job, max_running=1, max_inflight=2)
    executor.submit("d-1", _inputs("p-1"))

    with pytest.raises(SessionConflictError):
        executor.submit("d-2", _inputs("p-1"))

    # 거절된 요청이 대기열 자리를 쓰지 않았는지
    executor.submit("d-3", _inputs("p-2"))


def test_답변_대기로_끝나면_실행_자리를_반납한다(executors):
    def awaiting(product_id):
        return build_dummy_assessment(product_id).model_copy(update={
            "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
            "verification_status": FinalVerificationStatus.INCOMPLETE,
        })

    job = _GatedJob(result_for=awaiting)
    executor = _executor(executors, job, max_running=1, max_inflight=1)

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.AWAITING_INPUT)

    # 답변 대기 세션이 실행 자리·대기열을 차지하지 않으므로 다음 상품이 실행됨
    _wait_until(lambda: executor._inflight == 0)
    executor.submit("d-2", _inputs("p-2"))
    _wait_until(lambda: "p-2" in job.started)


def test_최대_시간을_넘긴_세션은_시간_초과로_끝내고_늦게_온_결과는_무시한다(executors):
    clock = _Clock()
    job = _GatedJob()
    executor = _executor(executors, job, clock=clock, max_duration=timedelta(minutes=10))
    executor.submit("d-1", _inputs("p-1"))
    _wait_until(lambda: "p-1" in job.started)

    clock.now = START + timedelta(minutes=9)
    assert executor.expire_overdue() == 0

    clock.now = START + timedelta(minutes=10)
    assert executor.expire_overdue() == 1
    session = executor.store.get("p-1")
    assert (session.status, session.error_code) == (SessionStatus.FAILED, ERROR_TIMEOUT)

    job.release("p-1")
    _wait_until(lambda: executor._inflight == 0)
    assert _status(executor.store, "p-1") is SessionStatus.FAILED


def test_시간_초과_뒤_재접수한_세션은_옛_실행이_덮어쓰지_않는다(executors):
    # #280 리뷰 재현: 시간 초과(failed) → 재접수(새 run_id로 running) → 옛 스레드 종료
    clock = _Clock()
    gates = {"old": threading.Event(), "new": threading.Event()}
    started = {"old": threading.Event(), "new": threading.Event()}

    def job(item, context, progress):
        label = "new" if started["old"].is_set() else "old"
        started[label].set()
        gates[label].wait(timeout=5)
        if label == "old":
            progress.stage(PipelineStage.VERIFICATION)
        result = build_dummy_assessment(item.product_id)
        return result.model_copy(update={"product": result.product.model_copy(update={"product_name": label})})

    executor = _executor(executors, job, clock=clock, max_duration=timedelta(minutes=10))
    executor.submit("d-1", _inputs("p-1"))
    started["old"].wait(timeout=5)
    clock.now = START + timedelta(minutes=10)
    executor.expire_overdue()

    executor.submit("d-2", _inputs("p-1"))
    started["new"].wait(timeout=5)
    new_run_id = executor.store.get("p-1").context.run_id

    # 옛 실행이 끝나도 새 세션의 단계·상태·결과는 그대로
    gates["old"].set()
    _wait_until(lambda: executor._inflight == 1)
    session = executor.store.get("p-1")
    assert (session.status, session.stage, session.result) == (SessionStatus.RUNNING, None, None)

    gates["new"].set()
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)
    session = executor.store.get("p-1")
    assert session.context.run_id == new_run_id
    assert session.result.product.product_name == "new"


def test_구독자_오류는_실행을_멈추지_않는다(executors):
    job = _GatedJob()
    executor = _executor(executors, job)
    executor.subscribe(lambda s: (_ for _ in ()).throw(RuntimeError("구독자 오류")))

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")

    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)
