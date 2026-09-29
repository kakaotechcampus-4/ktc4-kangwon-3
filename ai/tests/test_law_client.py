"""LawClient 본문 파싱을 실제 법제처 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.law import LawClient
from app.schemas.clients.law_request import LawTextRequest


def _client_returning(body: str) -> LawClient:
    client = LawClient()
    request = httpx.Request("GET", "https://www.law.go.kr/DRF/lawService.do")
    client._get = lambda path, params=None: httpx.Response(200, text=body, request=request)
    return client


def _full_size(body: str) -> str:
    # 3KB 미만 본문은 수신 실패로 처리되므로, 파싱만 보는 테스트는 주석으로 실제 본문 크기를 채운다.
    return body + "<!--" + " " * 4096 + "-->"


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

    result = _client_returning(_full_size(body)).get_law_text(LawTextRequest(mst="273575"))

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

    result = _client_returning(_full_size(body)).get_law_text(LawTextRequest(mst="273575"))

    assert [a.annex_type for a in result.annexes] == ["별표", "서식"]


def test_별표가_없는_문서는_빈_목록을_돌려준다():
    body = "<법령><조문><조문단위><조문번호>1</조문번호></조문단위></조문></법령>"

    result = _client_returning(_full_size(body)).get_law_text(LawTextRequest(mst="276591"))

    assert result.annexes == []


@pytest.mark.parametrize(
    "body",
    [
        # 없는 MST → 126B 안내 XML
        "<Law>일치하는 법령이 없습니다. 법령명을 확인하여 주십시오.</Law>",
        # 없는 행정규칙 ID → 138B 안내 XML
        "<Law>일치하는 행정규칙이 없습니다. 행정규칙명을 확인하여 주십시오.</Law>",
    ],
)
def test_3KB_미만_본문은_빈_결과_대신_수신_실패로_올린다(body):
    # 빈 결과로 넘기면 판정 단계가 "해당 규정 없음"으로 읽는다 (#183).
    with pytest.raises(RuntimeError, match="3KB 미만"):
        _client_returning(body).get_law_text(LawTextRequest(mst="999999999"))


def test_XML이_아닌_본문은_크기와_관계없이_수신_실패로_올린다():
    # licbyl 본문 요청은 3,225B짜리 HTML 껍데기가 와서 크기 기준만으로는 걸러지지 않는다.
    body = "<!DOCTYPE html><html><head><title>국가법령통합관리시스템</title></head><body>" + "&nbsp;" * 600
    with pytest.raises(RuntimeError, match="XML이 아닌 응답"):
        _client_returning(body).get_law_text(LawTextRequest(mst="18166257"))


def test_수신_실패_메시지에_target_일련번호_응답크기를_남긴다():
    body = "<Law>일치하는 법령이 없습니다. 법령명을 확인하여 주십시오.</Law>"

    with pytest.raises(RuntimeError) as exc_info:
        _client_returning(body).get_law_text(LawTextRequest(mst="999999999"))

    message = str(exc_info.value)
    assert "target=law" in message
    assert "id=999999999" in message
    assert f"{len(body.encode()):,}B" in message


def test_법령_본문의_기본정보를_파싱한다():
    # 법령ID를 MST 자리에 넣으면 다른 법(의장법) 본문이 정상으로 와서, 기본정보로만 대조할 수 있다 (#183).
    body = (
        "<법령><기본정보>"
        "<법령ID>008044</법령ID><법령명_한글>전기용품 및 생활용품 안전관리법 시행규칙</법령명_한글>"
        "<소관부처 소관부처코드=\"1451000\">산업통상부</소관부처><시행일자>20260827</시행일자>"
        "</기본정보><조문></조문></법령>"
    )

    result = _client_returning(_full_size(body)).get_law_text(LawTextRequest(mst="273575"))

    assert result.name == "전기용품 및 생활용품 안전관리법 시행규칙"
    assert result.document_id == "008044"
    assert result.enforce_date == "20260827"
    assert result.department == "산업통상부"


def test_행정규칙_본문의_기본정보를_파싱한다():
    body = (
        "<AdmRulService><행정규칙기본정보>"
        "<행정규칙명>전자상거래 등에서의 상품 등의 정보제공에 관한 고시</행정규칙명><행정규칙ID>2052005</행정규칙ID>"
        "<소관부처명>공정거래위원회</소관부처명><시행일자>20250101</시행일자>"
        "</행정규칙기본정보><조문내용>제1조(목적)</조문내용></AdmRulService>"
    )

    result = _client_returning(_full_size(body)).get_admrul_text(LawTextRequest(mst="2100000248568"))

    assert result.name == "전자상거래 등에서의 상품 등의 정보제공에 관한 고시"
    assert result.document_id == "2052005"
    assert result.enforce_date == "20250101"
    assert result.department == "공정거래위원회"
    assert len(result.articles) == 1
