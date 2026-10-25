"""외부 통신 클라이언트 공통 베이스(연결)와 공통 도구(키 가리기)를 검증한다."""

import socket
import sys

import httpx
import pytest

from app.clients import base
from app.clients.base import BaseClient, keepalive_socket_options, mask_sensitive_params


@pytest.fixture
def built_transports(monkeypatch) -> list[dict]:
    """BaseClient가 직접 만든 HTTPTransport의 생성 인자를 기록함."""
    built: list[dict] = []
    original = httpx.HTTPTransport
    monkeypatch.setattr(base.httpx, "HTTPTransport", lambda **kwargs: built.append(kwargs) or original(**kwargs))
    return built


def test_기본_연결은_keepalive_소켓_옵션과_httpx_기본_연결_한도를_건다(built_transports):
    BaseClient(base_url="https://api.example.test").close()

    [kwargs] = built_transports
    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in kwargs["socket_options"]
    assert kwargs["limits"] == httpx.Limits(max_connections=100, max_keepalive_connections=20)


def test_전송_계층을_주입하거나_감지를_끄면_소켓_옵션을_걸지_않는다(built_transports):
    BaseClient(base_url="https://api.example.test", transport=httpx.MockTransport(lambda r: httpx.Response(200))).close()
    BaseClient(base_url="https://api.example.test", dead_connection_seconds=None).close()

    assert built_transports == []


def test_윈도우는_keepalive_켜기만_건다():
    assert keepalive_socket_options(120, "win32") == ((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux 소켓 옵션은 Linux에서만 걸어 볼 수 있음")
def test_리눅스는_간격과_죽은_연결_상한까지_건다():
    options = keepalive_socket_options(90, "linux")

    assert (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60) in options
    assert (socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, 90_000) in options


def test_만들_때_넘긴_전송_계층으로_요청을_보낸다():
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    client = BaseClient(base_url="https://api.example.test", headers={"X-Test": "1"},
                        transport=httpx.MockTransport(record))
    client._client.get("/items")
    client.close()

    assert str(sent[0].url) == "https://api.example.test/items"
    assert sent[0].headers["X-Test"] == "1"


def test_mask_sensitive_params는_키_값만_대소문자_구분_없이_가린다():
    text = '근거 "https://x.kr/a?ServiceKey=k1&type=XML&oc=k2" 참고, serviceKey=k3'

    masked = mask_sensitive_params(text)

    assert masked == '근거 "https://x.kr/a?ServiceKey=***&type=XML&oc=***" 참고, serviceKey=k3'
