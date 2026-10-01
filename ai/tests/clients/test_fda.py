"""FdaClient 요청·응답 처리를 실제 식약처 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.fda import FdaClient
from app.schemas.clients.fda_request import CosmeticsReglRequest, MedicalDeviceRequest

# data.go.kr이 발급하는 인코딩된 키 형태 (+ → %2B)
ENCODED_KEY = "abc%2Bdef%3D%3D"


def _client(handler) -> FdaClient:
    client = FdaClient(service_key=ENCODED_KEY)
    client._client = httpx.Client(base_url="https://apis.data.go.kr", transport=httpx.MockTransport(handler))
    return client


def _json(body: dict):
    return lambda request: httpx.Response(200, json={"header": {"resultCode": "00"}, "body": body})


def test_의료기기는_items_item_중첩_구조를_풀고_키를_소문자로_바꾼다():
    body = {
        "totalCount": 213779,
        "items": [
            {"item": {"MDEQ_PRDLST_SN": "1", "PRDLST_NM": "체온계", "CLSF_NO_GRAD_CD": "2"}},
            "형식이 다른 항목",
        ],
    }

    result = _client(_json(body)).get_medical_devices(MedicalDeviceRequest())

    assert result.total_count == 213779
    assert len(result.items) == 1
    assert result.items[0].prdlst_nm == "체온계"
    assert result.items[0].clsf_no_grad_cd == "2"


def test_화장품_규제원료는_평평한_items의_키를_소문자로_바꾼다():
    body = {"totalCount": 7257, "items": [{"INGR_STD_NAME": "하이드로퀴논", "INGR_ENG_NAME": "Hydroquinone"}]}

    result = _client(_json(body)).get_cosmetics_regulations(CosmeticsReglRequest())

    assert result.total_count == 7257
    assert result.items[0].ingr_std_name == "하이드로퀴논"
    assert result.items[0].ingr_eng_name == "Hydroquinone"


def test_body가_비어_있으면_빈_목록을_돌려준다():
    result = _client(_json({})).get_cosmetics_regulations(CosmeticsReglRequest())

    assert result.total_count == 0
    assert result.items == []


def test_요청에는_디코딩한_키와_JSON_형식_페이지_파라미터를_보낸다():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"body": {}})

    _client(handler).get_medical_devices(MedicalDeviceRequest(page=3, num_of_rows=50))

    params = captured[0].url.params
    # 인코딩된 키를 그대로 보내면 httpx가 한 번 더 인코딩해 인증에 실패함
    assert params["serviceKey"] == "abc+def=="
    assert params["type"] == "json"
    assert params["pageNo"] == "3"
    assert params["numOfRows"] == "50"


def test_HTTP_오류_메시지에는_서비스_키가_노출되지_않는다():
    client = _client(lambda request: httpx.Response(500, text="server error"))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.get_medical_devices(MedicalDeviceRequest())

    message = str(exc_info.value)
    assert "serviceKey=***" in message
    assert "abc" not in message
