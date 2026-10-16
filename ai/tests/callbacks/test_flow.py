"""진단 세션 실행부터 콜백 발신함 전송까지 묶어서, 상품별 이벤트 순서를 확인한다."""

import threading

import pytest

from app.callbacks import CallbackOutbox, EventBuilder, SendResult, connect_callbacks
from app.observability.context import PipelineStage
from app.routers import _dummy
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicAssessmentDto, PublicQuestionDto
from app.schemas.schemas import ToolName
from app.sessions.executor import SessionExecutor
from app.sessions.store import SessionStore


class _Presenter:
    def assessment(self, result):
        return PublicAssessmentDto(status="completed", result_status="DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                                   summary=result.summary)

    def questions(self, result):
        return 1, [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


class _Sender:
    def __init__(self) -> None:
        self.events = []
        self._lock = threading.Lock()

    def send(self, event) -> SendResult:
        with self._lock:
            self.events.append(event)
        return SendResult(200)


@pytest.fixture
def flow(monkeypatch):
    # 가짜 진단의 단계별 지연을 없앰
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    sender = _Sender()
    executor = SessionExecutor(SessionStore(), _dummy.run_dummy_diagnosis, max_running=2)
    outbox = CallbackOutbox(sender, workers=2)
    connect_callbacks(executor, EventBuilder(_Presenter()), outbox)
    yield executor, outbox, sender
    executor.shutdown(wait=True)
    outbox.close(timeout=1)


def _inputs(*product_ids: str) -> list[ExtractionInput]:
    return [ExtractionInput(product_id=product_id, text_blocks=["상품 설명"]) for product_id in product_ids]


def test_상품마다_진행_이벤트_뒤에_결과_이벤트가_순서대로_나간다(flow):
    executor, outbox, sender = flow

    sessions = executor.submit("d-1", _inputs("p-1", "p-2", "p-3"))
    executor.shutdown(wait=True)
    assert outbox.close(timeout=5) == 0

    for session in sessions:
        run_id = session.context.run_id
        events = [event for event in sender.events if event.run_id == run_id]
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert [(event.event_type, getattr(event, "stage", None), getattr(event, "stage_status", None))
                for event in events] == [
            ("product_progress", "extraction", "started"),
            ("product_progress", "extraction", "completed"),
            ("product_progress", "selection", "started"),
            ("product_progress", "selection", "completed"),
            ("product_progress", "tool_execution", "started"),
            ("product_progress", "tool_execution", "completed"),
            ("product_progress", "aggregation", "started"),
            ("product_progress", "aggregation", "completed"),
            ("product_progress", "verification", "started"),
            ("product_progress", "verification", "completed"),
            ("product_progress", "finalization", "started"),
            ("product_result", None, None),
        ]
        assert {(event.diagnosis_id, event.product_id) for event in events} == {("d-1", session.context.product_id)}
    assert len({event.event_id for event in sender.events}) == len(sender.events)


def test_진단이_실패하면_실패_이벤트로_끝난다(monkeypatch, flow):
    executor, outbox, sender = flow

    def _broken(item, context, progress):
        raise RuntimeError("파이프라인 오류")

    monkeypatch.setattr(executor, "_job", _broken)
    executor.submit("d-1", _inputs("p-1"))
    executor.shutdown(wait=True)
    outbox.close(timeout=5)

    [event] = sender.events
    assert (event.event_type, event.error.code, event.error.retryable) == ("product_failed", "AI_PIPELINE_ERROR", False)


def test_진단서_변환이_실패하면_BE가_받는_마지막_이벤트는_실패다(monkeypatch):
    # AI 세션은 완료인데 마지막 이벤트가 빠지면 BE에서 진행 중으로 남음 (#321 리뷰)
    class _BrokenPresenter(_Presenter):
        def assessment(self, result):
            raise ValueError("미완료인데 안내가 없는 진단서")

    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    sender = _Sender()
    executor = SessionExecutor(SessionStore(), _dummy.run_dummy_diagnosis)
    outbox = CallbackOutbox(sender)
    connect_callbacks(executor, EventBuilder(_BrokenPresenter()), outbox)

    [session] = executor.submit("d-1", _inputs("p-1"))
    executor.shutdown(wait=True)
    outbox.close(timeout=5)

    last = sender.events[-1]
    assert executor.store.get("p-1").status.value == "completed"
    assert (last.event_type, last.stage, last.error.retryable) == ("product_failed", "finalization", False)
    assert [event.sequence for event in sender.events] == list(range(1, len(sender.events) + 1))


def test_여러_스레드가_같은_실행의_이벤트를_만들어도_발신함에는_번호_순서대로_들어간다():
    # 번호 발급 뒤 발신함에 넣기 전에 다른 스레드가 끼어들면 뒤 번호가 먼저 들어감 (병렬 Tool·시간 초과 정리)
    first_waiting, second_built = threading.Event(), threading.Event()

    class _Builder(EventBuilder):
        def build(self, session):
            events = super().build(session)
            if events and events[0].sequence == 2:
                second_built.set()
            return events

    class _Outbox:
        def __init__(self) -> None:
            self.sequences = []

        def put(self, events) -> None:
            if events and events[0].sequence == 1:
                first_waiting.set()
                # 잠금이 없으면 이 사이에 다음 번호가 먼저 들어옴
                second_built.wait(timeout=0.3)
            self.sequences.extend(event.sequence for event in events)

    class _Executor:
        def subscribe(self, listener) -> None:
            self.listener = listener

        def subscribe_tool(self, listener) -> None:
            pass

    store, executor, outbox = SessionStore(), _Executor(), _Outbox()
    connect_callbacks(executor, _Builder(_Presenter()), outbox)
    context = store.accept("d-1", ["p-1"])[0].context
    store.start(context)
    extraction = store.update_stage(context, PipelineStage.EXTRACTION)
    selection = store.update_stage(context, PipelineStage.SELECTION)

    first = threading.Thread(target=executor.listener, args=(extraction,))
    first.start()
    first_waiting.wait(timeout=1)
    second = threading.Thread(target=executor.listener, args=(selection,))
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert outbox.sequences == [1, 2, 3]


def test_Tool이_병렬로_진행을_알려도_BE에는_번호_순서대로_나간다(monkeypatch, flow):
    executor, outbox, sender = flow
    tools = [ToolName.ELECTRICAL, ToolName.RADIO, ToolName.CHILDREN]

    def _parallel_tools(item, context, progress):
        progress.stage(PipelineStage.TOOL_EXECUTION)

        def run_tool(tool_name):
            progress.tool(tool_name, "started")
            progress.tool(tool_name, "completed")

        threads = [threading.Thread(target=run_tool, args=(tool_name,)) for tool_name in tools]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        progress.stage(PipelineStage.AGGREGATION)
        return _dummy.build_dummy_assessment(item.product_id)

    monkeypatch.setattr(executor, "_job", _parallel_tools)
    executor.submit("d-1", _inputs("p-1"))
    executor.shutdown(wait=True)
    assert outbox.close(timeout=5) == 0

    events = sender.events
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    tool_events = [(event.tool_name, event.stage_status) for event in events if getattr(event, "tool_name", None)]
    for name in ("ELECTRICAL", "RADIO", "CHILDREN"):
        assert tool_events.index((name, "started")) < tool_events.index((name, "completed"))
    # Tool 진행은 Tool 실행 단계 시작과 완료 사이에만
    stages = [(event.stage, event.stage_status, event.tool_name)
              for event in events if event.event_type == "product_progress"]
    assert stages[0] == ("tool_execution", "started", None)
    assert stages[7] == ("tool_execution", "completed", None)
    assert len(tool_events) == 6
