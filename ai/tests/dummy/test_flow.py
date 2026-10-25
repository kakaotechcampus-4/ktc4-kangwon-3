"""시나리오 더미를 세션·콜백 발신함에 묶어, 흐름별로 BE가 받는 질문·재진단·결과·실패 콜백 순서를 확인한다."""

import threading
import time

import pytest

from app.callbacks import CallbackOutbox, EventBuilder, SendResult, connect_callbacks
from app.domain.context import RunType
from app.dummy import DummyFlow, DummyResult, DummyScenario, job, mark_scenario, run_scenario_diagnosis
from app.routers._dummy import DummyAssessmentPresenter
from app.schemas.agent import ExtractionInput
from app.sessions.manager import SessionManager
from app.sessions.store import SessionStore

# 실행 하나의 마지막 이벤트
_LAST = {"product_awaiting_input", "product_result", "product_failed"}


class _Sender:
    def __init__(self) -> None:
        self.events = []
        self._lock = threading.Lock()

    def send(self, event) -> SendResult:
        with self._lock:
            self.events.append(event)
        return SendResult(200)

    def last_of(self, run_id: str):
        with self._lock:
            return next((event for event in self.events if event.run_id == run_id and event.event_type in _LAST), None)


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setattr(job, "STAGE_SECONDS", 0)
    sender = _Sender()
    manager = SessionManager(SessionStore(), run_scenario_diagnosis)
    outbox = CallbackOutbox(sender)
    connect_callbacks(manager, EventBuilder(DummyAssessmentPresenter()), outbox)
    yield manager, sender
    manager.shutdown(wait=True)
    outbox.close(timeout=1)


def _wait_last(sender: _Sender, run_id: str, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while (event := sender.last_of(run_id)) is None:
        if time.monotonic() > deadline:
            raise AssertionError("마지막 이벤트를 기다리다 시간 초과")
        time.sleep(0.01)
    return event


def _play(flow, scenario: DummyScenario) -> list:
    """BE처럼 질문이 오면 모두 '네'로 답해 재진단하고, 실행마다 마지막 이벤트를 모아 돌려준다."""
    manager, sender = flow
    source = mark_scenario(ExtractionInput(product_id="p-1", text_blocks=["RC 보트"]), scenario)
    [session] = manager.submit("d-1", [source], run_type=RunType.DUMMY)
    lasts = [_wait_last(sender, session.context.run_id)]
    while lasts[-1].event_type == "product_awaiting_input":
        asked = lasts[-1]
        resumed = manager.resume(
            diagnosis_id="d-1", product_id="p-1", run_id=asked.run_id, question_round=asked.question_round,
            answers={question.question_key: "네" for question in asked.questions}, run_type=RunType.DUMMY,
        )
        lasts.append(_wait_last(sender, resumed.context.run_id))
    return lasts


@pytest.mark.parametrize(("flow_kind", "expected"), [
    (DummyFlow.NONE, ["product_result"]),
    (DummyFlow.ONE_ROUND, ["product_awaiting_input", "product_result"]),
    (DummyFlow.TWO_ROUNDS, ["product_awaiting_input", "product_awaiting_input", "product_result"]),
    (DummyFlow.FAILED, ["product_failed"]),
    (DummyFlow.FAILED_AFTER_ANSWER, ["product_awaiting_input", "product_failed"]),
])
def test_흐름대로_질문_재진단_결과_실패_콜백이_나간다(flow, flow_kind, expected):
    lasts = _play(flow, DummyScenario(flow=flow_kind, result=DummyResult.CERTIFICATION))

    assert [event.event_type for event in lasts] == expected
    # 실행마다 진행 이벤트부터 번호가 1로 시작해 빠짐없이 이어짐
    _, sender = flow
    for last in lasts:
        sequences = [event.sequence for event in sender.events if event.run_id == last.run_id]
        assert sequences == list(range(1, len(sequences) + 1))


def test_2회차_질문은_회차가_오르고_새_키만_묻는다(flow):
    first, second, result = _play(flow, DummyScenario(flow=DummyFlow.TWO_ROUNDS, result=DummyResult.CERTIFICATION))

    assert (first.question_round, second.question_round) == (1, 2)
    first_keys = {question.question_key for question in first.questions}
    assert not first_keys & {question.question_key for question in second.questions}
    # 두 회차 답변이 모두 결과 요약에 보임
    assert result.assessment.summary.count("→ 네") == len(first.questions) + len(second.questions)


def test_실패_콜백은_재시도_불가_파이프라인_오류다(flow):
    [failed] = _play(flow, DummyScenario(flow=DummyFlow.FAILED, result=DummyResult.CERTIFICATION))

    assert (failed.error.code, failed.error.retryable) == ("AI_PIPELINE_ERROR", False)


@pytest.mark.parametrize(("result", "expected"), [
    (DummyResult.ALLOWED, ("completed", "PURCHASING_AGENT_ALLOWED")),
    (DummyResult.CERTIFICATION, ("completed", "DIRECT_IMPORT_CERTIFICATION_REQUIRED")),
    (DummyResult.RECHECK, ("incomplete", "RECHECK_REQUIRED")),
])
def test_결과_종류마다_결과_콜백의_진단서_상태가_다르다(flow, result, expected):
    [*_, last] = _play(flow, DummyScenario(flow=DummyFlow.ONE_ROUND, result=result))

    assert last.event_type == "product_result"
    assert (last.assessment.status, last.assessment.result_status) == expected
