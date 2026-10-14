"""진단 세션 실행부터 콜백 발신함 전송까지 묶어서, 상품별 이벤트 순서를 확인한다."""

import threading

import pytest

from app.callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from app.routers import _dummy
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicAssessmentDto, PublicQuestionDto
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

    def send(self, event) -> int:
        with self._lock:
            self.events.append(event)
        return 200


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
