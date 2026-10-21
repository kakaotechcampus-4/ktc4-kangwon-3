"""공공데이터포털 공통 베이스(키 처리·결과코드 확인)를 실제 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.data_go_kr import DataGoKrClient

ENCODED_KEY = "abc%2Bdef%3D%3D"


class _FakeDataGoKrClient(DataGoKrClient[str, httpx.Response]):
    def _send(self, request: str) -> httpx.Response:
        return self._get_with_service_key("/1471000/fake", params={"q": request})

    def _parse(self, raw: httpx.Response) -> httpx.Response:
        return raw


def test_인코딩된_서비스_키는_한_번_디코딩해서_보낸다(wire):
    client = _FakeDataGoKrClient(service_key=ENCODED_KEY)
    sent = wire(client, lambda request: httpx.Response(200))

    client.fetch_raw("x")

    # 이중 인코딩되면 403 (키 미등록)
    assert sent[0].url.params["serviceKey"] == "abc+def=="
    assert sent[0].url.host == "apis.data.go.kr"


def test_HTTP_오류_메시지에는_서비스_키가_남지_않는다(wire):
    client = _FakeDataGoKrClient(service_key=ENCODED_KEY)
    wire(client, lambda request: httpx.Response(403))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.fetch_raw("x")

    assert "abc" not in str(exc_info.value)
    assert "serviceKey=***" in str(exc_info.value)


def test_결과코드_00은_통과한다():
    DataGoKrClient._raise_for_result_code("00", "NORMAL SERVICE.")


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("11", "NO MANDATORY REQUEST PARAMETERS ERROR! \n numOfRows maximum is =[500]"),
        ("22", "LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS ERROR."),
        (None, None),
    ],
)
def test_HTTP_200이어도_결과코드가_00이_아니면_예외를_올린다(code, message):
    # 그대로 넘기면 "0건"과 구분 안 됨
    with pytest.raises(RuntimeError, match=f"resultCode={code}"):
        DataGoKrClient._raise_for_result_code(code, message)


def test_결과코드_예외_메시지는_줄바꿈을_한_줄로_정리한다():
    with pytest.raises(RuntimeError) as exc_info:
        DataGoKrClient._raise_for_result_code("11", "ERROR! \n numOfRows maximum is =[500]")

    assert "\n" not in str(exc_info.value)
    assert "ERROR! numOfRows maximum is =[500]" in str(exc_info.value)
