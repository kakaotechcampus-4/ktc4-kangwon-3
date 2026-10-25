"""법제처 법령 본문 클라이언트를 실제 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.law import LawTextClient
from app.schemas.clients.law_request import LawTextRequest

_BASIC_INFO = (
    "<기본정보><법령ID>004698</법령ID><법령명_한글>전기용품 및 생활용품 안전관리법 시행령</법령명_한글>"
    "<법종구분 법종구분코드=\"A0103\">대통령령</법종구분><공포일자>20260127</공포일자><공포번호>36055</공포번호>"
    "<제개정구분>타법개정</제개정구분><시행일자>20260201</시행일자>"
    "<소관부처 소관부처코드=\"1450000\">산업통상부</소관부처></기본정보>"
)


def _law(articles: str = "", annexes: str = "") -> str:
    return f"<법령>{_BASIC_INFO}<조문>{articles}</조문>{f'<별표>{annexes}</별표>' if annexes else ''}</법령>"


def _unit(number: str, kind: str, content: str, inner: str = "") -> str:
    return f"<조문단위><조문번호>{number}</조문번호><조문여부>{kind}</조문여부><조문내용>{content}</조문내용>{inner}</조문단위>"


def _fetch(wire, body: str, mst: str = "282997"):
    client = LawTextClient(oc="my-oc")
    sent = wire(client, lambda request: httpx.Response(200, text=body))
    return client.fetch_parsed(LawTextRequest(mst=mst)), sent


def test_본문_요청은_target_law와_MST를_보낸다(wire):
    _, sent = _fetch(wire, _law())

    params = sent[0].url.params
    assert sent[0].url.path == "/DRF/lawService.do"
    assert (params["target"], params["MST"]) == ("law", "282997")


def test_기본정보는_버전키·법종구분·공포정보까지_담는다(wire):
    result, _ = _fetch(wire, _law())

    assert result.mst == "282997"        # 기본정보에 없어 요청값
    assert (result.name, result.document_id) == ("전기용품 및 생활용품 안전관리법 시행령", "004698")
    assert (result.law_type, result.promulgate_date, result.promulgate_number) == ("대통령령", "20260127", "36055")
    assert (result.revision_type, result.enforce_date, result.department) == ("타법개정", "20260201", "산업통상부")


def test_구획_제목_행은_조문에서_빼고_소속_편장절관으로_붙인다(wire):
    result, _ = _fetch(wire, _law(
        _unit("1", "전문", "제1장 총칙 &lt;개정 2010.12.30&gt;")
        + _unit("1", "전문", "제1절 통칙")
        + _unit("1", "조문", "제1조(목적)")
        + _unit("2", "전문", "제1관 세부")
        + _unit("2", "조문", "제2조(정의)")
        + _unit("3", "전문", "제2절 원칙")
        + _unit("3", "조문", "제3조(원칙)")
        + _unit("4", "전문", "제2장의2 무선기기")
        + _unit("4", "조문", "제4조(기기)")
    ))

    assert [(a.article_number, a.headings) for a in result.articles] == [
        ("1", ["제1장 총칙", "제1절 통칙"]),
        ("2", ["제1장 총칙", "제1절 통칙", "제1관 세부"]),
        # 상위 단계가 바뀌면 아래 단계는 비움
        ("3", ["제1장 총칙", "제2절 원칙"]),
        ("4", ["제2장의2 무선기기"]),
    ]
    assert all(a.article_is_exist == "조문" for a in result.articles)


def test_구획_제목_모양이_아닌_전문_행은_내용을_잃지_않게_조문으로_남긴다(wire):
    result, _ = _fetch(wire, _law(_unit("1", "전문", "알 수 없는 전문")))

    assert [a.article_content for a in result.articles] == ["알 수 없는 전문"]


# 원문 순서 ①[1. 2.] ② ④[1.[가.]] (#210)
_NESTED = (
    "<항><항번호>①</항번호><항내용>① 첫째 항</항내용>"
    "<호><호번호>1.</호번호><호내용>1. 첫째 항의 1호</호내용></호><호><호번호>2.</호번호><호내용>2. 첫째 항의 2호</호내용></호></항>"
    "<항><항번호>②</항번호><항내용>② 둘째 항</항내용></항>"
    "<항><항번호>④</항번호><항내용>④ 넷째 항</항내용>"
    "<호><호번호>1.</호번호><호내용>1. 넷째 항의 1호</호내용><목><목번호>가.</목번호><목내용>가. 1호의 가목</목내용></목></호></항>"
)


def test_항_호_목은_소속된_상위_아래에_중첩된다(wire):
    article = _fetch(wire, _law(_unit("4", "조문", "제4조(지정신청)", _NESTED)))[0].articles[0]

    assert [p.number for p in article.paragraphs] == ["①", "②", "④"]
    assert [i.number for i in article.paragraphs[0].items] == ["1.", "2."]
    assert article.paragraphs[1].items == []
    assert [s.number for s in article.paragraphs[2].items[0].sub_items] == ["가."]


def test_항번호_없이_호만_있는_항은_번호와_내용_없이_호만_담는다(wire):
    inner = "<항><호><호번호>1.</호번호><호내용>1. 첫째 용어</호내용></호></항>"
    paragraph = _fetch(wire, _law(_unit("2", "조문", "제2조(정의)", inner)))[0].articles[0].paragraphs[0]

    assert (paragraph.number, paragraph.content) == (None, None)
    assert [i.number for i in paragraph.items] == ["1."]


def test_가지번호가_있는_호는_번호가_같아도_가지번호로_구분한다(wire):
    # 4호와 4의2호의 호번호는 둘 다 "4." (#210)
    inner = ("<항><항번호>①</항번호><항내용>① 사유</항내용>"
             "<호><호번호>4.</호번호><호내용>4. 넷째</호내용></호>"
             "<호><호번호>4.</호번호><호가지번호>2</호가지번호><호내용>4의2. 넷째의2</호내용></호></항>")
    items = _fetch(wire, _law(_unit("5", "조문", "제5조(결격사유)", inner)))[0].articles[0].paragraphs[0].items

    assert [(i.number, i.branch_number) for i in items] == [("4.", None), ("4.", "2")]


def _annex(number: str, kind: str, title: str, links: str = "") -> str:
    return (f"<별표단위><별표번호>{number}</별표번호><별표가지번호>00</별표가지번호><별표구분>{kind}</별표구분>"
            f"<별표제목>{title}</별표제목><별표내용>{title} 내용</별표내용>{links}</별표단위>")


def test_별표는_조문과_별개로_담고_별표와_서식을_구분한다(wire):
    # 판정 대상 품목표는 조문이 아니라 별표에 있음
    result, _ = _fetch(wire, _law(_unit("1", "조문", "제1조(목적)"), _annex("0003", "별표", "안전인증대상제품") + _annex("0001", "서식", "신청서")))

    assert [(a.annex_number, a.annex_type, a.annex_title) for a in result.annexes] == [
        ("0003", "별표", "안전인증대상제품"), ("0001", "서식", "신청서")]
    assert result.annexes[0].annex_content == "안전인증대상제품 내용"


@pytest.mark.parametrize(("links", "expected"), [
    ("<별표서식파일링크>/LSW/flDownload.do?flSeq=1</별표서식파일링크><별표HWP파일명>a.hwp</별표HWP파일명>"
     "<별표서식PDF파일링크>/LSW/flDownload.do?flSeq=2</별표서식PDF파일링크><별표PDF파일명>a.pdf</별표PDF파일명>",
     ("https://www.law.go.kr/LSW/flDownload.do?flSeq=1", "hwp")),
    # HWP가 없으면 PDF
    ("<별표서식PDF파일링크>/LSW/flDownload.do?flSeq=2</별표서식PDF파일링크><별표PDF파일명>a.pdf</별표PDF파일명>",
     ("https://www.law.go.kr/LSW/flDownload.do?flSeq=2", "pdf")),
    # 형식은 짝인 파일명 확장자로
    ("<별표서식파일링크>/LSW/flDownload.do?flSeq=1</별표서식파일링크><별표HWP파일명>a.hwpx</별표HWP파일명>",
     ("https://www.law.go.kr/LSW/flDownload.do?flSeq=1", "hwpx")),
    ("<별표서식이미지파일링크>/LSW/flDownload.do?flSeq=3</별표서식이미지파일링크><별표이미지파일명>p.gif</별표이미지파일명>",
     ("https://www.law.go.kr/LSW/flDownload.do?flSeq=3", "gif")),
    ("", (None, None)),
])
def test_별표_파일_링크는_파싱_쉬운_형식_하나만_담는다(wire, links, expected):
    annex = _fetch(wire, _law(annexes=_annex("0003", "별표", "안전인증대상제품", links)))[0].annexes[0]

    assert (annex.file_url, annex.file_type) == expected


@pytest.mark.parametrize("body", [
    # 없는 MST → 안내 XML (#183: 빈 결과로 넘기면 "해당 규정 없음"으로 읽힘)
    "<Law>일치하는 법령이 없습니다. 법령명을 확인하여 주십시오.</Law>",
    # MST 빈 값 → XML로 파싱되는 XHTML 안내 페이지
    '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>국가법령정보센터</title></head><body/></html>',
])
def test_기본정보가_없는_응답은_빈_결과_대신_수신_실패로_올린다(wire, body):
    with pytest.raises(RuntimeError, match="기본정보 없음"):
        _fetch(wire, body, mst="999999999")


def test_수신_실패_메시지에_target_일련번호_응답크기_안내문을_남긴다(wire):
    body = "<Law>일치하는 법령이 없습니다. 법령명을 확인하여 주십시오.</Law>"

    with pytest.raises(RuntimeError) as exc_info:
        _fetch(wire, body, mst="999999999")

    message = str(exc_info.value)
    assert "target=law" in message and "id=999999999" in message
    assert f"{len(body.encode()):,}B" in message
    assert "루트 Law: 일치하는 법령이 없습니다" in message
