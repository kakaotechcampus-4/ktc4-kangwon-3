"""관세청 클라이언트의 HS 정규화·검증과 CLIP 검색 요청·응답을 실제 호출 없이 검증한다."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.clients.customs import CLIPClient
from app.schemas.clients.customs_request import CLIPSearchRequest, CustomsGwConfirmationRequest


@pytest.mark.parametrize(
    "raw_hs",
    [
        "8414.59-9000",
        "<em>8414</em>.59-9000",
    ],
)
def test_CLIP_HS는_숫자_10자리로_정규화한다(raw_hs):
    # 점이 남으면 세관장확인이 오류 없이 0건을 돌려준다 (#182).
    case = CLIPClient()._parse_item({"DTRM_HS_SGN": raw_hs})

    assert case.hs_code == "8414599000"


def test_정규화된_CLIP_HS는_세관장확인_요청에_그대로_들어간다():
    case = CLIPClient()._parse_item({"DTRM_HS_SGN": "3307.49-0000"})

    request = CustomsGwConfirmationRequest(hs_code=case.hs_code)

    assert request.hs_code == "3307490000"


@pytest.mark.parametrize(
    "hs_code",
    [
        "8414.599000",
        "8414",
        "84145990001",
        "",
    ],
)
def test_숫자_10자리가_아닌_HS는_세관장확인_요청에서_거부한다(hs_code):
    with pytest.raises(ValidationError):
        CustomsGwConfirmationRequest(hs_code=hs_code)


def _clip_item(doc_id: str) -> dict:
    return {
        "DOCID": doc_id,
        "DTRM_HS_SGN": "8414.59-9000",
        "CMDT_NM": "<em>휴대용</em> 선풍기",
        "CMDT_DESC": "충전식 소형 선풍기",
        "DTRM_RSN_CN": "전동기 내장 송풍기",
        "ENFR_DT": "20240101",
    }


def _clip_client(uls: dict, captured: list[dict] | None = None) -> CLIPClient:
    def fake_post(endpoint: str, data: dict) -> SimpleNamespace:
        if captured is not None:
            captured.append(data)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"uls_dmst": uls})

    client = CLIPClient()
    client._client.post = fake_post
    return client


def _clip_page(total_count: int, items: list[dict]) -> dict:
    return {"thisTotalCount": str(total_count), "itemList": items}


def test_CLIP_검색은_페이지_번호를_pageIndex로_보낸다():
    # initPageIndex·pagePerRecord는 서버가 무시해 항상 1페이지 10건 (#208)
    captured: list[dict] = []
    client = _clip_client(_clip_page(115, [_clip_item("d-11")]), captured)

    client.search(CLIPSearchRequest(query="마우스", page=2))

    assert captured == [{"prlstClsfCaseTpcd": "01", "srchYn": "Y", "srwr": "마우스", "pageIndex": "2"}]
    assert client._client.headers["X-Requested-With"] == "XMLHttpRequest"


def test_CLIP_검색_응답은_요청_페이지와_정리된_결정사례를_담는다():
    client = _clip_client(_clip_page(115, [_clip_item("d-1")]))

    result = client.search(CLIPSearchRequest(query="선풍기", page=3))

    assert result.page == 3
    assert result.total_count == 115
    assert result.items[0].doc_id == "d-1"
    assert result.items[0].hs_code == "8414599000"
    assert result.items[0].product_name == "휴대용 선풍기"


@pytest.mark.parametrize(
    ("page", "total_count", "item_count", "expected"),
    [
        (1, 115, 10, True),
        (11, 115, 10, True),
        (12, 115, 5, False),
        (11, 110, 10, False),
        (2, 115, 0, False),
    ],
)
def test_CLIP_다음_페이지_여부는_전체_건수와_빈_페이지로_판단한다(page, total_count, item_count, expected):
    items = [_clip_item(f"d-{i}") for i in range(item_count)]
    client = _clip_client(_clip_page(total_count, items))

    result = client.search(CLIPSearchRequest(query="마우스", page=page))

    assert result.has_next is expected


def test_CLIP_결과가_없으면_0건이고_다음_페이지가_없다():
    client = _clip_client({})

    result = client.search(CLIPSearchRequest(query="없는검색어"))

    assert result.total_count == 0
    assert result.items == []
    assert result.has_next is False
