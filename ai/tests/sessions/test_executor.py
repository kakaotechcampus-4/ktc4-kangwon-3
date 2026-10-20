"""진단 세션 실행기의 실행 상한·대기열·실패·시간 초과·진행 알림을 확인한다."""

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import SessionStatus
from app.sessions.errors import QueueFullError, SessionConflictError
from app.sessions.events import Completed, StageChanged, Started, ToolProgressed
from app.sessions.executor import SessionExecutor
from app.sessions.job import JobDone, JobFailed, JobNeedsInput
from app.sessions.store import SessionStore

START = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class _GatedJob:
    """release() 전까지 상품별로 붙잡아 두는 진단 함수."""

    def __init__(self, outcome_for=None, raise_error: bool = False) -> None:
        self.started: list[str] = []
        self.gates: dict[str, threading.Event] = {}
        self._outcome_for = outcome_for or (lambda product_id: JobDone(build_dummy_assessment(product_id)))
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
        return self._outcome_for(item.product_id)

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


def _awaiting_result(product_id: str):
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


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
    executor.subscribe(lambda e: seen.append((type(e), e.session.status, e.session.stage)))

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)

    assert seen == [
        (Started, SessionStatus.RUNNING, None),
        (StageChanged, SessionStatus.RUNNING, PipelineStage.EXTRACTION),
        (Completed, SessionStatus.COMPLETED, PipelineStage.EXTRACTION),
    ]


def test_진단_함수_예외는_재시도_불가_실패로_기록한다(executors):
    # 원인을 알 수 없는 예외는 코드 오류일 수 있어 BE가 재요청하지 않게 함 (#280 리뷰)
    job = _GatedJob(raise_error=True)
    executor = _executor(executors, job)

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.FAILED)

    session = executor.store.get("p-1")
    assert (session.error_code, session.retryable) == ("AI_PIPELINE_ERROR", False)


def test_진단_함수가_실패를_돌려주면_그_코드로_실패를_기록한다(executors):
    job = _GatedJob(outcome_for=lambda product_id: JobFailed("AI_INVALID_REQUEST", False))
    executor = _executor(executors, job)

    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.FAILED)

    session = executor.store.get("p-1")
    assert (session.error_code, session.retryable, session.result) == ("AI_INVALID_REQUEST", False, None)


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


def test_상품마다_실행_컨텍스트를_만들어_접수한다(executors):
    executor = _executor(executors, _GatedJob())

    sessions = executor.submit("d-1", _inputs("p-1", "p-2"))

    assert [s.context.product_id for s in sessions] == ["p-1", "p-2"]
    assert all(s.context.diagnosis_id == "d-1" for s in sessions)
    assert all(s.context.run_type is RunType.PRODUCTION for s in sessions)
    assert sessions[0].context.run_id != sessions[1].context.run_id
    assert all((s.status, s.accepted_at) == (SessionStatus.ACCEPTED, START) for s in sessions)


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


@pytest.mark.parametrize(("ahead", "status"), [
    (["blocker"], SessionStatus.ACCEPTED),   # 앞 상품이 실행 자리를 차지해 대기
    ([], SessionStatus.RUNNING),
])
def test_접수_또는_실행_중인_상품이_섞이면_요청_전체를_거절한다(executors, ahead, status):
    # #263: 진행 중 상품 포함 시 요청 전체 거절
    job = _GatedJob()
    executor = _executor(executors, job, max_running=1)
    for product_id in ahead:
        executor.submit("d-0", _inputs(product_id))
        _wait_until(lambda: product_id in job.started)
    executor.submit("d-1", _inputs("p-1"))
    _wait_until(lambda: _status(executor.store, "p-1") is status)

    with pytest.raises(SessionConflictError) as exc_info:
        executor.submit("d-2", _inputs("p-2", "p-1"))

    assert exc_info.value.product_ids == ["p-1"]
    assert executor.store.get("p-2") is None


def test_답변_대기_중인_상품도_새_접수를_막는다(executors):
    job = _GatedJob(outcome_for=lambda product_id: JobNeedsInput(_awaiting_result(product_id)))
    executor = _executor(executors, job)
    executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.AWAITING_INPUT)

    with pytest.raises(SessionConflictError):
        executor.submit("d-2", _inputs("p-1"))


@pytest.mark.parametrize("outcome_for", [
    lambda product_id: JobDone(build_dummy_assessment(product_id)),
    lambda product_id: JobFailed("AI_PIPELINE_ERROR", True),
])
def test_끝난_상품은_새_세션으로_다시_접수한다(executors, outcome_for):
    job = _GatedJob(outcome_for=outcome_for)
    executor = _executor(executors, job)
    [old] = executor.submit("d-1", _inputs("p-1"))
    job.release("p-1")
    _wait_until(lambda: executor._inflight == 0)

    [new] = executor.submit("d-2", _inputs("p-1"))

    assert new.status is SessionStatus.ACCEPTED
    assert new.context.run_id != old.context.run_id
    assert executor.store.get("p-1").context.run_id == new.context.run_id


def test_답변_대기로_끝나면_실행_자리를_반납한다(executors):
    job = _GatedJob(outcome_for=lambda product_id: JobNeedsInput(_awaiting_result(product_id)))
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
    assert (session.status, session.error_code) == (SessionStatus.FAILED, "AI_TIMEOUT")
    # 시간 초과는 대기·지연 같은 일시적 원인이라 재시도 가능
    assert session.retryable is True

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
        return JobDone(result.model_copy(update={"product": result.product.model_copy(update={"product_name": label})}))

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


def test_Tool_진행은_세션을_바꾸지_않고_이벤트만_낸다(executors):
    def job(item, context, progress):
        progress.stage(PipelineStage.TOOL_EXECUTION)
        progress.tool(ToolName.ELECTRICAL, "started")
        progress.tool(ToolName.ELECTRICAL, "completed")
        return JobDone(build_dummy_assessment(item.product_id))

    executor = _executor(executors, job)
    seen = []
    executor.subscribe(lambda e: seen.append((type(e), e.session.status, e.session.stage)))
    tools = []
    executor.subscribe(lambda e: isinstance(e, ToolProgressed) and tools.append((e.tool_name, e.status)))

    executor.submit("d-1", _inputs("p-1"))
    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)

    assert seen == [
        (Started, SessionStatus.RUNNING, None),
        (StageChanged, SessionStatus.RUNNING, PipelineStage.TOOL_EXECUTION),
        (ToolProgressed, SessionStatus.RUNNING, PipelineStage.TOOL_EXECUTION),
        (ToolProgressed, SessionStatus.RUNNING, PipelineStage.TOOL_EXECUTION),
        (Completed, SessionStatus.COMPLETED, PipelineStage.TOOL_EXECUTION),
    ]
    assert tools == [(ToolName.ELECTRICAL, "started"), (ToolName.ELECTRICAL, "completed")]


def test_시간_초과로_끝난_실행의_Tool_진행은_알리지_않고_경고로_남긴다(executors, caplog):
    clock = _Clock()
    gate, started = threading.Event(), threading.Event()

    def job(item, context, progress):
        started.set()
        gate.wait(timeout=5)
        progress.tool(ToolName.ELECTRICAL, "completed")
        return JobDone(build_dummy_assessment(item.product_id))

    executor = _executor(executors, job, clock=clock, max_duration=timedelta(minutes=10))
    tools = []
    executor.subscribe(lambda e: isinstance(e, ToolProgressed) and tools.append(e.tool_name))
    executor.submit("d-1", _inputs("p-1"))
    started.wait(timeout=5)
    clock.now = START + timedelta(minutes=10)
    executor.expire_overdue()

    gate.set()
    _wait_until(lambda: executor._inflight == 0)
    assert tools == []
    assert "세션 상태와 맞지 않는 변경 무시" in caplog.text


def test_Tool_진행_처리_중_구독자_오류는_실행을_멈추지_않는다(executors):
    def job(item, context, progress):
        progress.tool(ToolName.ELECTRICAL, "started")
        return JobDone(build_dummy_assessment(item.product_id))

    def broken(event):
        if isinstance(event, ToolProgressed):
            raise RuntimeError("구독자 오류")

    executor = _executor(executors, job)
    executor.subscribe(broken)

    executor.submit("d-1", _inputs("p-1"))

    _wait_until(lambda: _status(executor.store, "p-1") is SessionStatus.COMPLETED)


def test_개발용_진단은_dev_상품_ID로_진단서_없이_접수한다(executors):
    job = _GatedJob()
    executor = _executor(executors, job)

    session = executor.submit_dev(ExtractionInput(product_id="p-운영", text_blocks=["상품 설명"]))

    # 입력의 상품 ID는 쓰지 않고 운영 상품과 겹치지 않게 새로 발급
    assert session.context.product_id.startswith("dev-")
    assert (session.context.diagnosis_id, session.context.run_type) == (None, RunType.TEST)
    assert executor.store.get("p-운영") is None
    _wait_until(lambda: job.started)
    assert job.started == [session.context.product_id]
    job.release(session.context.product_id)
    _wait_until(lambda: _status(executor.store, session.context.product_id) is SessionStatus.COMPLETED)


def test_개발용_진단은_따로_정한_상한을_넘으면_거절하고_운영_접수는_막지_않는다(executors):
    job = _GatedJob()
    executor = _executor(executors, job, max_dev_inflight=2)
    first = executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))
    executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))

    with pytest.raises(QueueFullError, match="개발용"):
        executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))
    # 운영 진단은 개발용 상한과 관계없이 접수
    executor.submit("d-1", _inputs("p-1"))

    # 개발용 하나가 끝나면 다시 받음
    job.release(first.context.product_id)
    _wait_until(lambda: _status(executor.store, first.context.product_id) is SessionStatus.COMPLETED)
    _wait_until(lambda: len(executor._dev_runs) == 1)
    executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))


def test_개발용_진단도_전체_상한에_같이_센다(executors):
    executor = _executor(executors, _GatedJob(), max_inflight=2, max_dev_inflight=3)
    executor.submit("d-1", _inputs("p-1"))
    executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))

    with pytest.raises(QueueFullError):
        executor.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))
    with pytest.raises(QueueFullError):
        executor.submit("d-2", _inputs("p-2"))
