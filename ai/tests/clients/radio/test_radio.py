"""국립전파연구원 적합성평가 인증정보·유효여부 클라이언트를 실제 호출 없이 검증한다."""

import httpx
import pytest
from pydantic import ValidationError

from app.clients.radio import RadioAuthInfoClient, RadioAuthStatusClient
from app.schemas.clients.radio_request import RadioAuthRequest


def _xml(body: str):
    return lambda request: httpx.Response(200, text=body, headers={"content-type": "application/xml"})


_INFO = (
    "<GetAuthInfoResponse><bsmNm>REALTEK SEMICONDUCTOR CORP</bsmNm>"
    "<mtlNm>특정소출력 무선기기(무선랜을 포함한 무선접속시스템용 무선기기)</mtlNm>"
    "<matlBscMdlNm>RTL8852BE</matlBscMdlNm><mtlCefNo>R-C-RTK-RTL8852BE</mtlCefNo>"
    "<matlMfrNm>REALTEK SEMICONDUCTOR CORP</matlMfrNm><dtlInfCdNm>대만,베트남,중국</dtlInfCdNm>"
    "<cvaPcsYmd>2021-09-27</cvaPcsYmd><matlEtcMtr> </matlEtcMtr>"
    "<resultMsg>조회되었습니다.</resultMsg><resultCode>0000</resultCode></GetAuthInfoResponse>"
)


@pytest.mark.parametrize("client_cls", [RadioAuthInfoClient, RadioAuthStatusClient])
def test_https로_요청하고_브라우저_User_Agent를_붙인다(wire, client_cls):
    client = client_cls()
    sent = wire(client, _xml("<R><resultCode>0000</resultCode></R>"))

    client.fetch_raw(RadioAuthRequest(certification_number="R-C-RTK-RTL8852BE"))

    assert sent[0].url.scheme == "https"
    # UA 없으면 AWS에서 400 Request Blocked
    assert sent[0].headers["User-Agent"].startswith("Mozilla/5.0")


@pytest.mark.parametrize(
    ("number", "sent_value"),
    [
        (" R-C-RTK-RTL8852BE ", "R-C-RTK-RTL8852BE"),
        ("R C RTK RTL8852BE", "RCRTKRTL8852BE"),
        # 대소문자는 구분되고 공식 번호에도 소문자가 있어 바꾸지 않음
        ("R-C-es5-ESP32C3WROOM02", "R-C-es5-ESP32C3WROOM02"),
    ],
)
def test_인증번호의_공백은_지우고_대소문자는_그대로_보낸다(wire, number, sent_value):
    client = RadioAuthStatusClient()
    sent = wire(client, _xml("<R><resultCode>0000</resultCode></R>"))

    client.fetch_raw(RadioAuthRequest(certification_number=number))

    assert sent[0].url.params["mtlCefNo"] == sent_value


@pytest.mark.parametrize("number", ["", "   ", "\n"])
def test_비어_있는_인증번호는_요청_전에_거부한다(number):
    # 빈 값은 API가 0098 파라미터 오류를 정상 응답으로 돌려줌
    with pytest.raises(ValidationError):
        RadioAuthRequest(certification_number=number)


def test_인증정보는_풀어_쓴_필드로_옮기고_공백뿐인_값은_None으로_둔다(wire):
    client = RadioAuthInfoClient()
    wire(client, _xml(_INFO))

    info = client.fetch_parsed(RadioAuthRequest(certification_number="R-C-RTK-RTL8852BE"))

    assert (info.result_code, info.result_message) == ("0000", "조회되었습니다.")
    assert info.applicant_name == "REALTEK SEMICONDUCTOR CORP"
    assert info.model_name == "RTL8852BE"
    assert info.certification_number == "R-C-RTK-RTL8852BE"
    assert info.manufacture_country == "대만,베트남,중국"
    assert info.certified_date == "2021-09-27"
    assert info.remarks is None


def test_없는_인증번호는_HTTP_200이어도_결과코드_0001과_auth_status_N으로_구분된다(wire):
    client = RadioAuthStatusClient()
    wire(client, _xml(
        "<GetAuthStatusResponse><resultMsg>조회결과가 없습니다.</resultMsg>"
        "<resultCode>0001</resultCode><authYn>N</authYn></GetAuthStatusResponse>"
    ))

    status = client.fetch_parsed(RadioAuthRequest(certification_number="R-C-SEC-SM-S928N"))

    assert (status.result_code, status.auth_status) == ("0001", "N")
