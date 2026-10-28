"""LLM 게이트웨이 공유 연결: base_url마다 하나만 만들고, 닫으면 다시 만들고, 요청마다 측정 기록을 남기는지 확인한다."""

import contextlib
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.clients.llm import TIMEOUT_SECONDS, LlmClient, close_llm_clients, get_llm_client
from app.observability.measurements import ClientCall, measurement_sinks

BASE_URL = "https://mlapi.run/example/v1"


@pytest.fixture(autouse=True)
def _fresh_clients():
    close_llm_clients()
    yield
    close_llm_clients()


def test_같은_주소는_여러_스레드에서_불러도_연결_하나를_같이_쓴다():
    with ThreadPoolExecutor(max_workers=8) as pool:
        clients = list(pool.map(lambda _: get_llm_client(BASE_URL), range(32)))

    assert len({id(client) for client in clients}) == 1
    assert clients[0].http_client.timeout.read == TIMEOUT_SECONDS


def test_주소가_다르면_연결도_따로_만든다():
    assert get_llm_client(BASE_URL) is not get_llm_client("https://other.example/v1")


def test_닫으면_연결을_닫고_다음_호출에서_새로_만든다():
    first = get_llm_client(BASE_URL)

    close_llm_clients()

    assert first.http_client.is_closed
    assert get_llm_client(BASE_URL) is not first


def _raise(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc
    return handler


@pytest.mark.parametrize(("handler", "expected"), [
    (lambda request: httpx.Response(200, json={}), "ok"),
    (lambda request: httpx.Response(429), "http_error"),
    (_raise(httpx.ReadTimeout("느림")), "timeout"),
    (_raise(httpx.ConnectError("거부")), "connect_error"),
])
def test_보낸_요청마다_llm_결과와_시간을_측정_기록으로_남긴다(handler, expected):
    client = LlmClient(BASE_URL, transport=httpx.MockTransport(handler))
    calls: list[ClientCall] = []

    with measurement_sinks.added(calls.append), contextlib.suppress(httpx.HTTPError):
        client.http_client.post("/chat/completions", json={})

    assert [(call.api, call.result) for call in calls] == [("llm", expected)]
    client.close()
