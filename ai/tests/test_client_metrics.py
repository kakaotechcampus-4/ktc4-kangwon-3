"""외부 API 클라이언트 호출 지표를 실제 네트워크 없이 검증한다."""

import httpx
import pytest
from prometheus_client import REGISTRY

from app.clients.base import BaseClient, _InstrumentedClient
from app.clients.customs import CLIPClient
from app.schemas.clients.customs_request import CLIPSearchRequest


def _count(client: str, result: str) -> float:
    return REGISTRY.get_sample_value(
        "ai_external_api_requests_total", {"client": client, "result": result}
    ) or 0.0


def _duration_count(client: str) -> float:
    return REGISTRY.get_sample_value(
        "ai_external_api_request_duration_seconds_count", {"client": client}
    ) or 0.0


def _client(name: str, handler) -> _InstrumentedClient:
    return _InstrumentedClient(name, base_url="https://example.test", transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("status", "result"),
    [(200, "success"), (404, "http_error"), (500, "http_error"), (302, "http_error")],
)
def test_응답_상태코드에_따라_결과를_나눠_센다(status, result):
    # SafetyKorea는 인증 실패 시 302 반환
    name = f"StatusClient{status}"
    before = _count(name, result)

    _client(name, lambda request: httpx.Response(status)).get("/")

    assert _count(name, result) == before + 1
    assert _duration_count(name) >= 1


def test_타임아웃은_timeout으로_센다():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    before = _count("TimeoutClient", "timeout")

    with pytest.raises(httpx.ReadTimeout):
        _client("TimeoutClient", handler).get("/")

    assert _count("TimeoutClient", "timeout") == before + 1


def test_연결_실패는_connection_error로_센다():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    before = _count("ConnectClient", "connection_error")

    with pytest.raises(httpx.ConnectError):
        _client("ConnectClient", handler).get("/")

    assert _count("ConnectClient", "connection_error") == before + 1


def test_클라이언트_클래스_이름이_라벨로_붙는다():
    class SampleClient(BaseClient):
        pass

    client = SampleClient(base_url="https://example.test")

    assert isinstance(client._client, _InstrumentedClient)
    assert client._client._client_name == "SampleClient"


def test_post를_직접_부르는_클라이언트도_집계된다():
    # CLIPClient.search()는 _post를 거치지 않고 self._client.post를 직접 호출
    client = CLIPClient()
    body = {"uls_dmst": {"thisTotalCount": 0, "itemList": []}}
    client._client = _client("CLIPClient", lambda request: httpx.Response(200, json=body))
    before = _count("CLIPClient", "success")

    client.search(CLIPSearchRequest(query="선풍기"))

    assert _count("CLIPClient", "success") == before + 1
