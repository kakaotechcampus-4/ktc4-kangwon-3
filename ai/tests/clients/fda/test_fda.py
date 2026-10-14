"""식약처 의료기기·화장품 규제원료 클라이언트를 실제 호출 없이 검증한다."""

import httpx
import pytest
from pydantic import ValidationError

from app.clients.fda import CosmeticsRegulationClient, MedicalDeviceClient
from app.schemas.clients.fda_request import CosmeticsRegulationRequest, MedicalDeviceRequest

_OK_HEADER = {"resultCode": "00", "resultMsg": "NORMAL SERVICE."}


def _json(body: dict, header: dict = _OK_HEADER):
    return lambda request: httpx.Response(200, json={"header": header, "body": body})


def test_요청에는_JSON_형식과_페이지_번호·건수를_보낸다(wire):
    client = MedicalDeviceClient(service_key="key")
    sent = wire(client, _json({"totalCount": 0}))

    client.fetch_raw(MedicalDeviceRequest(page=3, num_of_rows=500))

    params = sent[0].url.params
    assert (params["type"], params["pageNo"], params["numOfRows"]) == ("json", "3", "500")


def test_의료기기는_items_item_중첩을_풀고_원문_키를_풀어_쓴_필드로_옮긴다(wire):
    client = MedicalDeviceClient(service_key="key")
    wire(client, _json({"totalCount": 214003, "items": [{"item": {
        "MDEQ_PRDLST_SN": "220000001", "PRDLST_NM": "안경렌즈", "MEDDEV_ITEM_NO": "수허 06-652 호",
        "PRMSN_DCLR_DIVS_NM": "신고", "CLSF_NO_GRAD_CD": "1", "MNFT_CLNT_NM": "Synthes GmbH.",
        "MNSC_NM": "CHEMILENS CO., LTD.", "MNSC_NATN_CD": "중국", "RTRCN_DSCTN_DT": "2024-06-26",
    }}]}))

    result = client.fetch_parsed(MedicalDeviceRequest())

    assert result.total_count == 214003
    item = result.items[0]
    assert (item.item_serial_number, item.item_name, item.approval_number) == ("220000001", "안경렌즈", "수허 06-652 호")
    assert (item.approval_type, item.grade) == ("신고", "1")
    assert (item.manufacturing_client_name, item.manufacturer_name, item.manufacture_country) == (
        "Synthes GmbH.", "CHEMILENS CO., LTD.", "중국")
    # 취소·취하 품목도 거르지 않고 일자로 구분
    assert item.cancellation_date == "2024-06-26"


def test_화장품_규제원료의_국가는_쉼표_문자열을_목록으로_나눈다(wire):
    client = CosmeticsRegulationClient(service_key="key")
    wire(client, _json({"totalCount": 7257, "items": [{
        "INGR_STD_NAME": "2,4,5-트라이메틸아닐린", "INGR_ENG_NAME": "2,4,5-Trimethylaniline",
        "PROH_NATIONAL": "EU,대만,아세안", "LIMIT_NATIONAL": None,
    }]}))

    item = client.fetch_parsed(CosmeticsRegulationRequest()).items[0]

    assert (item.ingredient_name, item.ingredient_english_name) == ("2,4,5-트라이메틸아닐린", "2,4,5-Trimethylaniline")
    assert item.prohibited_countries == ["EU", "대만", "아세안"]
    assert item.restricted_countries == []


@pytest.mark.parametrize(("text", "expected"), [("EU, 중국 ,", ["EU", "중국"]), ("", []), (None, []), ("한국", ["한국"])])
def test_국가_문자열은_공백과_빈_항목을_버린다(text, expected):
    assert CosmeticsRegulationClient._split_countries(text) == expected


def test_마지막_페이지_다음은_items_없이_와도_빈_목록이다(wire):
    client = MedicalDeviceClient(service_key="key")
    wire(client, _json({"totalCount": 214003}))

    assert client.fetch_parsed(MedicalDeviceRequest(page=99999)).items == []


def test_HTTP_200이어도_결과코드가_00이_아니면_예외를_올린다(wire):
    client = CosmeticsRegulationClient(service_key="key")
    wire(client, _json({}, {"resultCode": "11", "resultMsg": "numOfRows maximum is =[500]"}))

    with pytest.raises(RuntimeError, match="resultCode=11"):
        client.fetch_parsed(CosmeticsRegulationRequest())


@pytest.mark.parametrize("num_of_rows", [0, 501])
def test_페이지당_건수는_API_최대값인_500까지만_허용한다(num_of_rows):
    # 501부터는 API가 HTTP 200에 resultCode 11과 빈 목록을 돌려줌
    with pytest.raises(ValidationError):
        MedicalDeviceRequest(num_of_rows=num_of_rows)
