"""진단 세션 실행부터 콜백 발신함 전송까지 묶어서, 상품별 이벤트 순서를 확인한다."""

import threading
import time

import pytest

from app.callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from app.clients.backend import SendResult
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.routers import _dummy
from app.schemas.agent import ExtractionInput
from app.schemas.base import utc_now
from app.schemas.callback import PublicAssessmentDto, PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import DiagnosisSession
from app.sessions.job import JobDone, JobNeedsInput
from app.sessions.manager import SessionManager
from app.sessions.store import SessionStore
from app.sessions.transitions import ChangeStage, Start, apply


class _Presenter:
    def assessment(self, result):
        return PublicAssessmentDto(status="completed", result_status="DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                                   summary=result.summary)

    def questions(self, result):
        return [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


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
    manager = SessionManager(SessionStore(), _dummy.run_dummy_diagnosis, max_running=2)
    outbox = CallbackOutbox(sender, workers=2)
    connect_callbacks(manager, EventBuilder(_Presenter()), outbox)
    yield manager, outbox, sender
    manager.shutdown(wait=True)
    outbox.close(timeout=1)


def _inputs(*product_ids: str) -> list[ExtractionInput]:
    return [ExtractionInput(product_id=product_id, text_blocks=["상품 설명"]) for product_id in product_ids]


def test_상품마다_진행_이벤트_뒤에_결과_이벤트가_순서대로_나간다(flow):
    manager, outbox, sender = flow

    sessions = manager.submit("d-1", _inputs("p-1", "p-2", "p-3"))
    manager.shutdown(wait=True)
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
    manager, outbox, sender = flow

    def _broken(job_input, context, progress):
        raise RuntimeError("파이프라인 오류")

    monkeypatch.setattr(manager, "_job", _broken)
    manager.submit("d-1", _inputs("p-1"))
    manager.shutdown(wait=True)
    outbox.close(timeout=5)

    [event] = sender.events
    assert (event.event_type, event.error.code, event.error.retryable) == ("product_failed", "AI_PIPELINE_ERROR", False)


def test_질문_뒤_재진단은_새_runId로_sequence를_1부터_보내고_결과로_끝난다(monkeypatch, flow):
    manager, outbox, sender = flow

    def _ask_then_finish(job_input, context, progress):
        progress.stage(PipelineStage.EXTRACTION)
        result = _dummy.build_dummy_assessment(job_input.source.product_id)
        if job_input.answers:
            return JobDone(result)
        return JobNeedsInput(result.model_copy(update={
            "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
            "verification_status": FinalVerificationStatus.INCOMPLETE,
        }), _Presenter().questions(result))

    monkeypatch.setattr(manager, "_job", _ask_then_finish)
    [first] = manager.submit("d-1", _inputs("p-1"))
    deadline = time.monotonic() + 5
    while manager.get("p-1").status.value != "awaiting_input":
        assert time.monotonic() < deadline
        time.sleep(0.01)
    second = manager.resume(
        diagnosis_id="d-1", product_id="p-1", run_id=first.context.run_id, question_round=1,
        answers={"battery_only": "네"},
    )
    manager.shutdown(wait=True)
    assert outbox.close(timeout=5) == 0

    by_run = {
        run_id: [(event.sequence, event.event_type) for event in sender.events if event.run_id == run_id]
        for run_id in (first.context.run_id, second.context.run_id)
    }
    assert by_run[first.context.run_id] == [(1, "product_progress"), (2, "product_awaiting_input")]
    assert by_run[second.context.run_id] == [(1, "product_progress"), (2, "product_result")]


def test_진단서_변환이_실패하면_BE가_받는_마지막_이벤트는_실패다(monkeypatch):
    # AI 세션은 완료인데 마지막 이벤트가 빠지면 BE에서 진행 중으로 남음 (#321 리뷰)
    class _BrokenPresenter(_Presenter):
        def assessment(self, result):
            raise ValueError("미완료인데 안내가 없는 진단서")

    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    sender = _Sender()
    manager = SessionManager(SessionStore(), _dummy.run_dummy_diagnosis)
    outbox = CallbackOutbox(sender)
    connect_callbacks(manager, EventBuilder(_BrokenPresenter()), outbox)

    [session] = manager.submit("d-1", _inputs("p-1"))
    manager.shutdown(wait=True)
    outbox.close(timeout=5)

    last = sender.events[-1]
    assert manager.get("p-1").status.value == "completed"
    assert (last.event_type, last.stage, last.error.retryable) == ("product_failed", "finalization", False)
    assert [event.sequence for event in sender.events] == list(range(1, len(sender.events) + 1))


def test_여러_스레드가_같은_실행의_이벤트를_만들어도_발신함에는_번호_순서대로_들어간다():
    # 번호 발급 뒤 발신함에 넣기 전에 다른 스레드가 끼어들면 뒤 번호가 먼저 들어감 (병렬 Tool·시간 초과 정리)
    first_waiting, second_built = threading.Event(), threading.Event()

    class _Builder(EventBuilder):
        def build(self, event):
            events = super().build(event)
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

    class _Manager:
        def subscribe(self, listener) -> None:
            self.listener = listener

    manager, outbox = _Manager(), _Outbox()
    connect_callbacks(manager, _Builder(_Presenter()), outbox)
    now = utc_now()
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    [source] = _inputs("p-1")
    session = apply(
        DiagnosisSession(context=context, source=source, accepted_at=now, updated_at=now), Start(), now=now,
    ).session
    [extraction] = apply(session, ChangeStage(PipelineStage.EXTRACTION), now=now).events
    [selection] = apply(extraction.session, ChangeStage(PipelineStage.SELECTION), now=now).events

    first = threading.Thread(target=manager.listener, args=(extraction,))
    first.start()
    first_waiting.wait(timeout=1)
    second = threading.Thread(target=manager.listener, args=(selection,))
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert outbox.sequences == [1, 2, 3]


def test_Tool이_병렬로_진행을_알려도_BE에는_번호_순서대로_나간다(monkeypatch, flow):
    manager, outbox, sender = flow
    tools = [ToolName.ELECTRICAL, ToolName.RADIO, ToolName.CHILDREN]

    def _parallel_tools(job_input, context, progress):
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
        return JobDone(_dummy.build_dummy_assessment(job_input.source.product_id))

    monkeypatch.setattr(manager, "_job", _parallel_tools)
    manager.submit("d-1", _inputs("p-1"))
    manager.shutdown(wait=True)
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


def test_개발용_진단은_진행부터_결과까지_콜백을_보내지_않는다(flow):
    manager, outbox, sender = flow

    session = manager.submit_dev(ExtractionInput(product_id="x", text_blocks=["상품 설명"]))
    manager.shutdown(wait=True)
    outbox.close(timeout=5)

    assert manager.get(session.context.product_id).status.value == "completed"
    assert sender.events == []
