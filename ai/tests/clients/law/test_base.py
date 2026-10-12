"""법제처 공통 베이스(OC 필수·오류 응답·파일 링크 고르기)를 실제 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.law.base import LawGoKrClient


class _FakeLawClient(LawGoKrClient[str, str]):
    def _send(self, request: str) -> httpx.Response:
        return self._get_with_oc("/DRF/lawSearch.do", params={"target": "law", "query": request})

    def _parse(self, raw: httpx.Response) -> str:
        return self._parse_root(raw).tag


def _xml(body: str, status: int = 200):
    return lambda request: httpx.Response(status, text=body)


@pytest.mark.parametrize("oc", ["", "   ", None])
def test_OC가_비어_있으면_만들_때_거부한다(oc):
    # "test" 같은 기본값으로 돌지 않게 함
    with pytest.raises(ValueError, match="OC"):
        _FakeLawClient(oc)


def test_요청에는_OC와_XML_형식을_붙인다(wire):
    client = _FakeLawClient("my-oc")
    sent = wire(client, _xml("<LawSearch/>"))

    client.fetch_raw("전파법")

    params = sent[0].url.params
    assert (params["OC"], params["type"], params["query"]) == ("my-oc", "XML", "전파법")


def test_HTTP_오류_메시지에는_OC가_남지_않는다(wire):
    client = _FakeLawClient("my-oc")
    wire(client, _xml("x", status=500))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.fetch_raw("전파법")

    assert "my-oc" not in str(exc_info.value)


def test_HTTP_200의_Response_오류_응답은_예외로_올린다(wire):
    client = _FakeLawClient("my-oc")
    wire(client, _xml("<Response><result>사용자 정보 검증에 실패하였습니다.</result><msg>IP 등록 필요</msg></Response>"))

    with pytest.raises(RuntimeError, match="사용자 정보 검증에 실패"):
        client.fetch_parsed("전파법")


def test_XML이_아닌_응답은_수신_실패로_올린다(wire):
    client = _FakeLawClient("my-oc")
    wire(client, _xml("<!DOCTYPE html><html><body>" + "&nbsp;" * 10))

    with pytest.raises(RuntimeError, match="XML이 아닌 응답"):
        client.fetch_parsed("전파법")


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        ([("/LSW/a?flSeq=1", "hwp"), ("/LSW/a?flSeq=2", "pdf")], ("https://www.law.go.kr/LSW/a?flSeq=2", "pdf")),
        ([(None, "pdf"), ("/LSW/a?flSeq=1", "hwp")], ("https://www.law.go.kr/LSW/a?flSeq=1", "hwp")),
        ([("http://law.go.kr/x?1", "zip"), ("http://law.go.kr/x?2", "hwpx"), ("http://law.go.kr/x?3", "xlsx")],
         ("http://law.go.kr/x?3", "xlsx")),
        ([("", "pdf"), ("  ", "hwp")], (None, None)),
    ],
)
def test_파일_링크는_파싱_쉬운_형식_하나를_완전한_주소로_고른다(candidates, expected):
    # 우선순위 PDF → XLSX → HWPX → HWP → 이미지 → ZIP
    assert LawGoKrClient._pick_file(candidates) == expected


@pytest.mark.parametrize(("filename", "expected"), [("a.PDF", "pdf"), ("고시전문_최종.hwpx\n", "hwpx"), ("noext", None), (None, None)])
def test_파일_형식은_파일명_확장자에서_꺼낸다(filename, expected):
    assert LawGoKrClient._file_type(filename) == expected
