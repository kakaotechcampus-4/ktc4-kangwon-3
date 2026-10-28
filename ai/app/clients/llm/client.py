"""LLM 게이트웨이 연결. 채팅·임베딩 모델이 같은 연결을 쓰도록 base_url마다 하나만 만든다."""

from collections.abc import Iterator
from threading import Lock
from time import perf_counter

import httpx

from ...observability.measurements import ClientCall, measurement_sinks
from ..base import DEAD_CONNECTION_SECONDS, BaseClient, keepalive_transport

# 요청 하나의 대기 상한(초). 모델 호출에 그대로 넘김
TIMEOUT_SECONDS = 45.0

_clients: dict[str, "LlmClient"] = {}
_lock = Lock()


class _MeasuredTransport(httpx.BaseTransport):
    """보낸 HTTP 요청마다 결과·시간을 측정 기록으로 남기는 전송 계층.

    모델 SDK가 연결로 직접 요청하므로 RequestClient의 조회 기록을 거치지 않음.
    event hook은 시간 초과·연결 실패 때 안 불려서 전송 계층에서 잼. SDK 재시도는 시도마다 기록됨.
    스트리밍 응답은 헤더 뒤에도 본문이 이어 오므로 본문을 다 읽고 닫을 때 기록 (받다 끊기면 실패로 기록).
    """

    def __init__(self, inner: httpx.BaseTransport, api: str) -> None:
        self._inner = inner
        self._api = api

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        call = _Call(self._api)
        try:
            response = self._inner.handle_request(request)
        except httpx.TimeoutException:
            call.record("timeout")
            raise
        except httpx.TransportError:
            call.record("connect_error")
            raise
        result = "http_error" if response.status_code >= 400 else "ok"
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=_MeasuredStream(response.stream, call, result),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self._inner.close()


class _Call:
    """요청 1건의 측정. 시작 시각을 들고 있다가 결과를 한 번만 기록함."""

    def __init__(self, api: str) -> None:
        self._api = api
        self._started = perf_counter()
        self._recorded = False

    def record(self, result: str) -> None:
        """결과를 측정 기록으로 남긴다. 이미 남겼으면 무시.

        Args:
            result: 호출 결과 (ok·http_error·timeout·connect_error).
        """
        if self._recorded:
            return
        self._recorded = True
        measurement_sinks.publish(ClientCall(api=self._api, result=result, seconds=perf_counter() - self._started))


class _MeasuredStream(httpx.SyncByteStream):
    """응답 본문을 그대로 넘기고, 다 읽고 닫을 때나 받다 실패할 때 기록하는 본문 스트림."""

    def __init__(self, inner: httpx.SyncByteStream, call: _Call, result: str) -> None:
        self._inner = inner
        self._call = call
        self._result = result

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self._inner
        except httpx.TimeoutException:
            self._call.record("timeout")
            raise
        except httpx.TransportError:
            self._call.record("connect_error")
            raise

    def close(self) -> None:
        try:
            self._inner.close()
        finally:
            self._call.record(self._result)


class LlmClient(BaseClient):
    """OpenAI 호환 게이트웨이 연결. 요청은 LangChain 모델이 이 연결로 보냄.

    보낸 HTTP 요청마다 api="llm"으로 결과·시간을 측정 기록으로 남김.

    Args:
        base_url: 게이트웨이 주소 (OPENAI_BASE_URL).
        transport: httpx 전송 계층. 테스트에서 가짜 응답을 붙일 때 주입.
    """

    API = "llm"

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        inner = transport or keepalive_transport(DEAD_CONNECTION_SECONDS)
        super().__init__(base_url=base_url, timeout=TIMEOUT_SECONDS, transport=_MeasuredTransport(inner, self.API))

    @property
    def http_client(self) -> httpx.Client:
        """모델(ChatOpenAI·OpenAIEmbeddings)의 http_client로 넘길 연결."""
        return self._client


def get_llm_client(base_url: str) -> LlmClient:
    """base_url의 공유 연결. 없으면 만든다. 여러 스레드가 같이 불러도 하나만 만듦.

    Args:
        base_url: 게이트웨이 주소.

    Returns:
        LlmClient: 공유 연결.
    """
    with _lock:
        if base_url not in _clients:
            _clients[base_url] = LlmClient(base_url)
        return _clients[base_url]


def close_llm_clients() -> None:
    """공유 연결을 모두 닫고 비운다. 서버 종료 때 부름 (다시 부르면 새로 만듦)."""
    with _lock:
        for client in _clients.values():
            client.close()
        _clients.clear()
