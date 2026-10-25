"""케이스 더미를 세션·콜백 발신함에 묶어, 케이스별로 BE가 받는 질문·재진단·결과·실패 콜백 순서를 확인한다."""

import threading
import time

import pytest

from app.callbacks import CallbackOutbox, EventBuilder, SendResult, connect_callbacks
from app.domain.context import RunType
from app.dummy import DummyCaseName, job, mark_case, run_scenario_diagnosis
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


def _play(flow, case: DummyCaseName) -> list:
    """BE처럼 질문이 오면 모두 '네'로 답해 재진단하고, 실행마다 마지막 이벤트를 모아 돌려준다."""
    manager, sender = flow
    source = mark_case(ExtractionInput(product_id="p-1", text_blocks=["상품 설명"]), case)
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


_ASK, _RESULT, _FAILED = "product_awaiting_input", "product_result", "product_failed"


@pytest.mark.parametrize(("case", "expected_events", "expected_status"), [
    (DummyCaseName.KC_FAN, [_RESULT], "PURCHASING_AGENT_ALLOWED"),
    (DummyCaseName.POWER_BANK, [_ASK, _RESULT], "DIRECT_IMPORT_CERTIFICATION_REQUIRED"),
    (DummyCaseName.RC_BOAT, [_ASK, _ASK, _RESULT], "DIRECT_IMPORT_CERTIFICATION_REQUIRED"),
    (DummyCaseName.CHARGING_PAD, [_ASK, _RESULT], "RECHECK_REQUIRED"),
    (DummyCaseName.TOY_GUN, [_RESULT], "DIRECT_IMPORT_CERTIFICATION_REQUIRED"),
    (DummyCaseName.TUMBLER, [_ASK, _ASK, _RESULT], "DIRECT_IMPORT_CERTIFICATION_REQUIRED"),
    (DummyCaseName.DIFFUSER, [_RESULT], "RECHECK_REQUIRED"),
    # 3회차 질문은 세션이 질문 한도 초과 미완료 결과로 바꿈
    (DummyCaseName.QUESTION_LIMIT, [_ASK, _ASK, _RESULT], "RECHECK_REQUIRED"),
    (DummyCaseName.FAILED, [_FAILED], None),
    (DummyCaseName.FAILED_AFTER_ANSWER, [_ASK, _FAILED], None),
])
def test_케이스대로_질문_재진단_결과_실패_콜백이_나간다(flow, case, expected_events, expected_status):
    lasts = _play(flow, case)

    assert [event.event_type for event in lasts] == expected_events
    assert getattr(getattr(lasts[-1], "assessment", None), "result_status", None) == expected_status
    # 실행마다 진행 이벤트부터 번호가 1로 시작해 빠짐없이 이어짐
    _, sender = flow
    for last in lasts:
        sequences = [event.sequence for event in sender.events if event.run_id == last.run_id]
        assert sequences == list(range(1, len(sequences) + 1))


def test_2회차_질문은_회차가_오르고_새_키만_묻는다(flow):
    first, second, result = _play(flow, DummyCaseName.RC_BOAT)

    assert (first.question_round, second.question_round) == (1, 2)
    first_keys = {question.question_key for question in first.questions}
    assert not first_keys & {question.question_key for question in second.questions}
    # 두 회차 답변이 모두 결과 요약에 보임
    assert result.assessment.summary.count("→ 네") == len(first.questions) + len(second.questions)


def test_질문_한도를_넘긴_케이스는_안내와_함께_미완료로_끝난다(flow):
    *_, result = _play(flow, DummyCaseName.QUESTION_LIMIT)

    assert result.assessment.status == "incomplete"
    assert any("직접 확인" in notice for notice in result.assessment.notices)


def test_실패_콜백은_재시도_불가_파이프라인_오류다(flow):
    [failed] = _play(flow, DummyCaseName.FAILED)

    assert (failed.error.code, failed.error.retryable) == ("AI_PIPELINE_ERROR", False)
