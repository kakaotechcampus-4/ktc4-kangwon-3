"""법령 변경 중 보낼 것을 고르고 BE 형식으로 바꿔 재시도 규칙대로 보내는지 확인한다."""

import logging
from datetime import date

import pytest

from app.callbacks.law_changes import LawChangeNotifier, to_callback_request
from app.clients.backend import CallbackTransportError, SendResult
from app.db import LawChange, LawChangeKind, LawVersion
from app.observability.measurements import CallbackOutcome, measurement_sinks
from app.schemas.schemas import ToolName
from app.tools.common.law_sources import LAW_SOURCES

VERSION = LawVersion("291321", "20261020", "20260420", "일부개정")


def _change(kind=LawChangeKind.APPLIED, *, version=VERSION, tool=ToolName.CHILDREN.value, previous="280000"):
    return LawChange(kind, "어린이제품 안전 특별법 시행규칙", "012345", False, tool, version, previous)


def test_적용_판이_바뀐_변경을_BE_형식으로_바꾼다():
    request = to_callback_request([_change()])

    assert request.model_dump(mode="json", by_alias=True) == {
        "changes": [{
            "lawName": "어린이제품 안전 특별법 시행규칙", "documentId": "012345", "admrul": False,
            "toolName": "CHILDREN", "serialNumber": "291321", "previousSerialNumber": "280000",
            "revisionType": "일부개정", "enforceDate": "2026-10-20", "issuedDate": "2026-04-20",
        }],
    }


def test_새_판_발표와_건너뛴_판은_보내지_않는다():
    changes = [_change(LawChangeKind.ANNOUNCED, previous=None), _change(), _change(LawChangeKind.SKIPPED, previous=None)]

    request = to_callback_request(changes)

    assert len(request.changes) == 1


def test_보낼_변경이_없으면_요청을_만들지_않는다():
    changes = [_change(LawChangeKind.ANNOUNCED, previous=None), _change(LawChangeKind.SKIPPED, previous=None)]

    assert to_callback_request(changes) is None
    assert to_callback_request([]) is None


@pytest.mark.parametrize("tool", list(ToolName))
def test_분야_이름을_BE_enum_이름으로_바꾼다(tool):
    request = to_callback_request([_change(tool=tool.value)])

    assert request.changes[0].tool_name == tool.name


def test_날짜가_없으면_비워서_보낸다():
    request = to_callback_request([_change(version=LawVersion("291321", None, "", None))])

    dto = request.changes[0]
    assert (dto.enforce_date, dto.issued_date, dto.revision_type) == (None, None, None)


def test_날짜_형식이_깨지면_비우고_나머지는_그대로_보낸다(caplog):
    request = to_callback_request([_change(version=LawVersion("291321", "2026-10", "20260420"))])

    dto = request.changes[0]
    assert (dto.enforce_date, dto.issued_date) == (None, date(2026, 4, 20))
    assert "2026-10" in caplog.text


@pytest.mark.parametrize("source", LAW_SOURCES, ids=lambda source: source.name)
def test_모든_근거_문서가_BE_형식과_길이_제한에_맞는다(source):
    # BE는 길이를 넘는 값이 하나라도 있으면 묶음 전체를 거절함 (lawName 255자, documentId 50자)
    change = LawChange(LawChangeKind.APPLIED, source.name, source.document_id, source.is_admrul, source.tool, VERSION)

    dto = to_callback_request([change]).changes[0]

    assert len(dto.law_name) <= 255
    assert len(dto.document_id) <= 50
    assert dto.tool_name == source.tool.name


class _Sender:
    """정해 둔 응답을 차례로 돌려주는 가짜 BE. 예외면 그대로 던짐."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


OK = SendResult(200, "OK")
SERVER_ERROR = SendResult(503)
TIMEOUT = CallbackTransportError("시간 초과")


def _notify(sender, changes=None, *, wait=None, **kwargs):
    """변경을 보내고 기다린 시간과 측정 기록을 돌려준다."""
    delays, records = [], []

    def record_wait(seconds):
        delays.append(seconds)
        return False

    notifier = LawChangeNotifier(sender, wait=wait or record_wait, **kwargs)
    with measurement_sinks.added(records.append):
        notifier([_change()] if changes is None else changes)
    return delays, records


def test_성공하면_한_번만_보내고_결과를_기록한다():
    sender = _Sender(OK)

    delays, records = _notify(sender)

    assert len(sender.requests) == 1
    assert delays == []
    assert records == [CallbackOutcome("law_changes", True, retries=0)]


def test_보낼_변경이_없으면_보내지_않는다():
    sender = _Sender()

    _, records = _notify(sender, [_change(LawChangeKind.SKIPPED, previous=None)])

    assert sender.requests == []
    assert records == []


def test_재시도_간격은_30초부터_2배씩_늘고_상한은_5분이다():
    sender = _Sender(*[SERVER_ERROR] * 6)

    delays, _ = _notify(sender)

    assert delays == [30, 60, 120, 240, 300]
    assert len(sender.requests) == 6


@pytest.mark.parametrize("failure", [
    TIMEOUT, SERVER_ERROR, SendResult(409, "COMMON-003"), SendResult(409, "COMMON-009"), SendResult(500, "COMMON-003"),
], ids=["전송_실패", "5xx", "동시_저장_겹침", "락_대기_초과", "겹침이_500으로_와도"])
def test_다시_보내면_되는_실패는_재시도하고_성공하면_횟수를_기록한다(failure):
    sender = _Sender(failure, OK)

    delays, records = _notify(sender)

    assert len(sender.requests) == 2
    assert delays == [30]
    assert records == [CallbackOutcome("law_changes", True, retries=1)]


@pytest.mark.parametrize("rejected", [
    SendResult(400, "COMMON-001"), SendResult(401, "COMMON-004"), SendResult(404),
], ids=["형식_거절", "인증_실패", "경로_없음"])
def test_다시_보내도_안_되는_거절은_바로_포기한다(rejected, caplog):
    sender = _Sender(rejected)

    with caplog.at_level(logging.ERROR):
        delays, records = _notify(sender)

    assert len(sender.requests) == 1
    assert delays == []
    assert records == [CallbackOutcome("law_changes", False, retries=0, drop_reason="not_retryable")]


def test_끝까지_못_보내면_재전송에_쓸_값을_오류_로그로_남기고_예외는_내지_않는다(caplog):
    sender = _Sender(*[TIMEOUT] * 6)

    with caplog.at_level(logging.ERROR):
        _, records = _notify(sender)

    assert records == [CallbackOutcome("law_changes", False, retries=5, drop_reason="retry_exhausted")]
    [log] = [record for record in caplog.records if record.levelno == logging.ERROR]
    message = log.getMessage()
    assert all(value in message for value in ("어린이제품 안전 특별법 시행규칙", "012345", "291321"))


def test_예상하지_못한_오류는_재시도하지_않고_기록한다():
    sender = _Sender(ValueError("이상한 응답"))

    delays, records = _notify(sender)

    assert delays == []
    assert records == [CallbackOutcome("law_changes", False, retries=0, drop_reason="error")]


def test_재시도_대기_중_종료되면_더_보내지_않는다():
    sender = _Sender(SERVER_ERROR)

    _, records = _notify(sender, wait=lambda seconds: True)

    assert len(sender.requests) == 1
    assert records == [CallbackOutcome("law_changes", False, retries=0, drop_reason="shutdown")]


def test_close하면_기다리던_재시도가_바로_끝난다():
    # 실제 대기 함수를 씀. close가 없으면 30초를 기다림
    sender = _Sender(SERVER_ERROR)
    records = []
    notifier = LawChangeNotifier(sender)
    notifier.close()

    with measurement_sinks.added(records.append):
        notifier([_change()])

    assert records == [CallbackOutcome("law_changes", False, retries=0, drop_reason="shutdown")]
