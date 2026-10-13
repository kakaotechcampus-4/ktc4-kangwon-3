"""세관장확인대상물품 GW 클라이언트를 실제 호출 없이 검증한다."""

import httpx
import pytest
from pydantic import ValidationError

from app.clients.customs import CustomsGwClient
from app.schemas.clients.customs_request import CustomsGwConfirmationRequest

_OK = (
    "<response><header><resultCode>00</resultCode><resultMsg>정상서비스.</resultMsg></header>"
    "<body><items><item>"
    "<aplyStrtDt>20200406</aplyStrtDt><bfhnAffcRtmTpcd>2</bfhnAffcRtmTpcd>"
    "<dcerCfrmLworCd>23</dcerCfrmLworCd><dcerCfrmLworNm>전기용품 및 생활용품 안전관리법</dcerCfrmLworNm>"
    "<hsSgn>8516710000</hsSgn><reqApreIttCd>105</reqApreIttCd><reqApreIttNm>기술표준원</reqApreIttNm>"
    "<reqCfrmIstmNm>전기용품 및 생활용품 요건확인서</reqCfrmIstmNm>"
    "</item></items></body></response>"
)


def _xml(body: str):
    return lambda request: httpx.Response(200, text=body, headers={"content-type": "application/xml"})


def test_요청에는_HS코드와_수출입_구분을_보낸다(wire):
    client = CustomsGwClient(service_key="key")
    sent = wire(client, _xml(_OK))

    client.fetch_raw(CustomsGwConfirmationRequest(hs_code="8516710000"))

    params = sent[0].url.params
    assert (params["hsSgn"], params["imexTpcd"]) == ("8516710000", "2")


def test_응답은_법령·요건확인기관·제출서류로_옮긴다(wire):
    client = CustomsGwClient(service_key="key")
    wire(client, _xml(_OK))

    item = client.fetch_parsed(CustomsGwConfirmationRequest(hs_code="8516710000")).items[0]

    assert (item.hs_code, item.law_code, item.law_name) == ("8516710000", "23", "전기용품 및 생활용품 안전관리법")
    assert (item.req_agency_code, item.req_agency_name) == ("105", "기술표준원")
    # reqCfrmIstmNm은 기관명이 아니라 제출 서류명
    assert item.req_document_name == "전기용품 및 생활용품 요건확인서"
    assert item.apply_start_date == "20200406"


def test_확인대상이_없는_HS는_빈_목록이다(wire):
    client = CustomsGwClient(service_key="key")
    wire(client, _xml("<response><header><resultCode>00</resultCode></header><body><items/></body></response>"))

    assert client.fetch_parsed(CustomsGwConfirmationRequest(hs_code="9999999999")).items == []


def test_HTTP_200이어도_결과코드가_00이_아니면_예외를_올린다(wire):
    client = CustomsGwClient(service_key="key")
    wire(client, _xml(
        "<response><header><resultCode>22</resultCode>"
        "<resultMsg>LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS ERROR.</resultMsg></header><body/></response>"
    ))

    with pytest.raises(RuntimeError, match="resultCode=22"):
        client.fetch_parsed(CustomsGwConfirmationRequest(hs_code="8516710000"))


@pytest.mark.parametrize("hs_code", ["8414.599000", "8414", "84145990001", "", "903289"])
def test_숫자_10자리가_아닌_HS는_요청_전에_거부한다(hs_code):
    # 점이 남으면 오류 없이 0건 (#182)
    with pytest.raises(ValidationError):
        CustomsGwConfirmationRequest(hs_code=hs_code)
