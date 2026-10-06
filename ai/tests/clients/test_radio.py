"""RadioClient 요청·응답 처리를 실제 전파연구원 호출 없이 검증한다."""

import httpx

from app.clients.radio import RadioClient
from app.schemas.clients.radio_request import RadioAuthRequest

BASE_URL = "http://emsit.go.kr/openapi/service/AuthenticationInfoService"


def _client(handler) -> RadioClient:
    client = RadioClient()
    client._client = httpx.Client(
        base_url=BASE_URL, headers=client._client.headers, transport=httpx.MockTransport(handler)
    )
    return client


def _xml(body: str):
    return lambda request: httpx.Response(200, text=body)


def test_인증정보를_파싱한다():
    body = (
        "<GetAuthInfoResponse>"
        "<resultMsg>정상</resultMsg><resultCode>0000</resultCode>"
        "<bsmNm>주식회사 예시</bsmNm><mtlNm>블루투스 이어폰</mtlNm><matlBscMdlNm>BT-100</matlBscMdlNm>"
        "<mtlCefNo>R-C-ABC-BT100</mtlCefNo><dtlInfCdNm>중국</dtlInfCdNm><cvaPcsYmd>2025-01-02</cvaPcsYmd>"
        "</GetAuthInfoResponse>"
    )

    result = _client(_xml(body)).get_auth_info(RadioAuthRequest(mtl_cef_no="R-C-ABC-BT100"))

    assert result.result_code == "0000"
    assert result.mtl_nm == "블루투스 이어폰"
    assert result.matl_bsc_mdl_nm == "BT-100"
    assert result.dtl_inf_cd_nm == "중국"
    assert result.matl_mfr_nm is None


def test_없는_인증번호는_HTTP_200이어도_결과코드_0001로_구분된다():
    # 실제 API 응답 형태 (없는 번호도 HTTP 200)
    body = (
        "<GetAuthStatusResponse>"
        "<resultMsg>조회결과가 없습니다.</resultMsg><resultCode>0001</resultCode><authYn>N</authYn>"
        "</GetAuthStatusResponse>"
    )

    result = _client(_xml(body)).get_auth_status(RadioAuthRequest(mtl_cef_no="XX-NOT-EXIST-000"))

    assert result.result_code == "0001"
    assert result.auth_yn == "N"


def test_공백뿐인_태그는_None으로_돌려준다():
    body = "<GetAuthInfoResponse><resultMsg>정상</resultMsg><resultCode>0000</resultCode><bsmNm>  </bsmNm></GetAuthInfoResponse>"

    result = _client(_xml(body)).get_auth_info(RadioAuthRequest(mtl_cef_no="R-C-ABC-BT100"))

    assert result.bsm_nm is None


def test_요청에는_인증번호와_브라우저_User_Agent를_보낸다():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text="<GetAuthStatusResponse><resultCode>0000</resultCode><resultMsg>정상</resultMsg></GetAuthStatusResponse>")

    _client(handler).get_auth_status(RadioAuthRequest(mtl_cef_no="R-C-ABC-BT100"))

    request = captured[0]
    assert request.url.path.endswith("/getAuthStatus.do")
    assert request.url.params["mtlCefNo"] == "R-C-ABC-BT100"
    # 브라우저 User-Agent가 없으면 거부되는 API
    assert "Mozilla/5.0" in request.headers["User-Agent"]
