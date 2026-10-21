"""CLIP 품목분류 결정사례 클라이언트를 실제 호출 없이 검증한다."""

import json
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from app.clients.customs import CLIPClient
from app.schemas.clients.customs_request import CLIPSearchRequest


def _item(doc_id: str, hs: str = "8414.59-9000") -> dict:
    return {
        "DTRM_HS_SGN": hs,
        "CMDT_NM": "<em>전기</em> 선풍기",
        "CMDT_DESC": "가정용 <span><strong class=\"engnehighlight\">선풍기</strong></span> ...",
        "DTRM_RSN_CN": "결정 이유 ...",
        "DOCID": doc_id,
        "ENFR_DT": "20240101",
    }


def _page(current: int, per_page: int, total: int, items: list[dict]) -> dict:
    return {
        "paginationInfo": {"currentPageNo": current, "recordCountPerPage": per_page, "totalRecordCount": total},
        "uls_dmst": {"thisTotalCount": total, "itemList": items},
    }


def _responding(body: dict):
    # 본문은 JSON인데 Content-Type은 text/html로 옴
    return lambda request: httpx.Response(200, text=json.dumps(body), headers={"content-type": "text/html"})


def test_검색은_form으로_국내사례_검색어_페이지를_보내고_필수_헤더를_붙인다(wire):
    client = CLIPClient()
    sent = wire(client, _responding(_page(2, 50, 115, [_item("d-1")])))

    client.fetch_raw(CLIPSearchRequest(query="선풍기", page=2, page_size=50))

    form = {key: values[0] for key, values in parse_qs(sent[0].content.decode()).items()}
    assert sent[0].method == "POST"
    # 페이지 번호·건수는 pageIndex·pageUnit만 인식 (#245)
    assert form == {"prlstClsfCaseTpcd": "01", "srchYn": "Y", "srwr": "선풍기", "pageIndex": "2", "pageUnit": "50"}
    assert sent[0].headers["X-Requested-With"] == "XMLHttpRequest"


def test_검색_결과는_태그를_지우고_서버가_적용한_페이지_정보로_다음_페이지를_정한다(wire):
    client = CLIPClient()
    wire(client, _responding(_page(2, 50, 115, [_item("d-1")])))

    result = client.fetch_parsed(CLIPSearchRequest(query="선풍기", page=2, page_size=50))

    assert (result.page, result.total_count, result.has_next) == (2, 115, True)
    case = result.items[0]
    assert case.product_name == "전기 선풍기"
    assert "<" not in case.description
    assert (case.doc_id, case.enforce_date) == ("d-1", "20240101")


@pytest.mark.parametrize(
    ("current", "per_page", "total", "items", "has_next"),
    [(3, 50, 115, [_item("d")], False), (1, 10, 0, [], False), (2, 10, 115, [], False)],
)
def test_마지막_페이지거나_빈_페이지면_다음_페이지가_없다(wire, current, per_page, total, items, has_next):
    client = CLIPClient()
    wire(client, _responding(_page(current, per_page, total, items)))

    assert client.fetch_parsed(CLIPSearchRequest(query="x")).has_next is has_next


@pytest.mark.parametrize(
    ("raw_hs", "expected"),
    [
        ("8414.59-9000", ["8414599000"]),
        ("<em>8414</em>.59-9000", ["8414599000"]),
        # 구성품별로 따로 분류된 사례: 이어 붙이지 않고 목록으로
        ("①8509.80-9000\r\n②8506.10-2000", ["8509809000", "8506102000"]),
        ("①9403.20-9000, ②③8537.10-2000, ④8471.60-3090", ["9403209000", "8537102000", "8471603090"]),
        ("8544.41-2090\r\n8544.49-2090", ["8544412090", "8544492090"]),
        # 6단위까지만 결정된 사례는 6자리 그대로
        ("9032.89", ["903289"]),
        ("", []),
    ],
)
def test_결정_HS는_코드마다_숫자만_남긴_목록으로_나눈다(raw_hs, expected):
    assert CLIPClient()._parse_hs_codes(raw_hs) == expected


@pytest.mark.parametrize("page_size", [0, 101])
def test_페이지당_건수는_1부터_100까지만_허용한다(page_size):
    with pytest.raises(ValidationError):
        CLIPSearchRequest(query="x", page_size=page_size)
