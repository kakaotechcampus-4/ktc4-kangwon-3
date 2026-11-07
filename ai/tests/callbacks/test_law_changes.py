"""법령 변경 중 보낼 것을 고르고 BE 형식으로 바꾸는지 확인한다."""

from datetime import date

import pytest

from app.callbacks.law_changes import to_callback_request
from app.db import LawChange, LawChangeKind, LawVersion
from app.schemas.schemas import ToolName
from app.tools.common.law_sources import LAW_SOURCES

CHECKED_ON = date(2026, 11, 7)
VERSION = LawVersion("291321", "20261020", "20260420", "일부개정")


def _change(kind=LawChangeKind.APPLIED, *, version=VERSION, tool=ToolName.CHILDREN.value, previous="280000"):
    return LawChange(kind, "어린이제품 안전 특별법 시행규칙", "012345", False, tool, version, previous)


def test_적용_판이_바뀐_변경을_BE_형식으로_바꾼다():
    request = to_callback_request([_change()], CHECKED_ON)

    assert request.model_dump(mode="json", by_alias=True) == {
        "checkedOn": "2026-11-07",
        "changes": [{
            "lawName": "어린이제품 안전 특별법 시행규칙", "documentId": "012345", "admrul": False,
            "toolName": "CHILDREN", "serialNumber": "291321", "previousSerialNumber": "280000",
            "revisionType": "일부개정", "enforceDate": "2026-10-20", "issuedDate": "2026-04-20",
        }],
    }


def test_새_판_발표와_건너뛴_판은_보내지_않는다():
    changes = [_change(LawChangeKind.ANNOUNCED, previous=None), _change(), _change(LawChangeKind.SKIPPED, previous=None)]

    request = to_callback_request(changes, CHECKED_ON)

    assert len(request.changes) == 1


def test_보낼_변경이_없으면_요청을_만들지_않는다():
    changes = [_change(LawChangeKind.ANNOUNCED, previous=None), _change(LawChangeKind.SKIPPED, previous=None)]

    assert to_callback_request(changes, CHECKED_ON) is None
    assert to_callback_request([], CHECKED_ON) is None


@pytest.mark.parametrize("tool", list(ToolName))
def test_분야_이름을_BE_enum_이름으로_바꾼다(tool):
    request = to_callback_request([_change(tool=tool.value)], CHECKED_ON)

    assert request.changes[0].tool_name == tool.name


def test_날짜가_없으면_비워서_보낸다():
    request = to_callback_request([_change(version=LawVersion("291321", None, "", None))], CHECKED_ON)

    dto = request.changes[0]
    assert (dto.enforce_date, dto.issued_date, dto.revision_type) == (None, None, None)


def test_날짜_형식이_깨지면_비우고_나머지는_그대로_보낸다(caplog):
    request = to_callback_request([_change(version=LawVersion("291321", "2026-10", "20260420"))], CHECKED_ON)

    dto = request.changes[0]
    assert (dto.enforce_date, dto.issued_date) == (None, date(2026, 4, 20))
    assert "2026-10" in caplog.text


@pytest.mark.parametrize("source", LAW_SOURCES, ids=lambda source: source.name)
def test_모든_근거_문서가_BE_형식과_길이_제한에_맞는다(source):
    # BE는 길이를 넘는 값이 하나라도 있으면 묶음 전체를 거절함 (lawName 255자, documentId 50자)
    change = LawChange(LawChangeKind.APPLIED, source.name, source.document_id, source.is_admrul, source.tool, VERSION)

    dto = to_callback_request([change], CHECKED_ON).changes[0]

    assert len(dto.law_name) <= 255
    assert len(dto.document_id) <= 50
    assert dto.tool_name == source.tool.name
