"""LawClient 본문 파싱을 실제 법제처 호출 없이 검증한다."""

import httpx

from app.clients.law import LawClient
from app.schemas.clients.law_request import LawTextRequest


def _client_returning(body: str) -> LawClient:
    client = LawClient()
    request = httpx.Request("GET", "https://www.law.go.kr/DRF/lawService.do")
    client._get = lambda path, params=None: httpx.Response(200, text=body, request=request)
    return client


def test_법령_본문의_별표를_조문과_함께_파싱한다():
    # 판정 대상 품목표(안전확인대상제품 등)는 조문이 아니라 시행규칙 별표에 있다.
    body = (
        "<법령>"
        "<조문><조문단위><조문번호>1</조문번호><조문내용>제1조(목적)</조문내용></조문단위></조문>"
        "<별표>"
        "<별표단위><별표번호>0004</별표번호><별표가지번호>00</별표가지번호><별표구분>별표</별표구분>"
        "<별표제목>안전확인대상제품</별표제목><별표내용>13) 전지(충전지만 해당한다)</별표내용></별표단위>"
        "<별표단위><별표번호>0014</별표번호><별표가지번호>00</별표가지번호><별표구분>서식</별표구분>"
        "<별표제목>안전확인신고서</별표제목><별표내용>신고서 양식</별표내용></별표단위>"
        "</별표>"
        "</법령>"
    )

    result = _client_returning(body).get_law_text(LawTextRequest(mst="273575"))

    assert len(result.articles) == 1
    assert len(result.annexes) == 2
    annex = result.annexes[0]
    assert annex.annex_number == "0004"
    assert annex.annex_branch_number == "00"
    assert annex.annex_title == "안전확인대상제품"
    assert "전지" in annex.annex_content


def test_별표구분으로_품목표와_서식을_구분할_수_있다():
    # "안전인증…"으로 시작하는 제목에도 서식(지정신청서 등)이 섞여 있어 제목만으로는 거를 수 없다.
    body = (
        "<법령><조문></조문><별표>"
        "<별표단위><별표번호>0003</별표번호><별표구분>별표</별표구분><별표제목>안전인증대상제품</별표제목></별표단위>"
        "<별표단위><별표번호>0001</별표번호><별표구분>서식</별표구분><별표제목>안전인증기관 지정신청서</별표제목></별표단위>"
        "</별표></법령>"
    )

    result = _client_returning(body).get_law_text(LawTextRequest(mst="273575"))

    assert [a.annex_type for a in result.annexes] == ["별표", "서식"]


def test_별표가_없는_문서는_빈_목록을_돌려준다():
    body = "<법령><조문><조문단위><조문번호>1</조문번호></조문단위></조문></법령>"

    result = _client_returning(body).get_law_text(LawTextRequest(mst="276591"))

    assert result.annexes == []
