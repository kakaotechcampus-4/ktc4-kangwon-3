"""LLM 게이트웨이 연결. 채팅·임베딩 모델이 같은 연결을 쓰도록 base_url마다 하나만 만든다."""

from threading import Lock

import httpx

from ..base import BaseClient

# 요청 하나의 대기 상한(초). 모델 호출에 그대로 넘김
TIMEOUT_SECONDS = 45.0

_clients: dict[str, "LlmClient"] = {}
_lock = Lock()


class LlmClient(BaseClient):
    """OpenAI 호환 게이트웨이 연결. 요청은 LangChain 모델이 이 연결로 보냄.

    Args:
        base_url: 게이트웨이 주소 (OPENAI_BASE_URL).
        transport: httpx 전송 계층. 테스트에서 가짜 응답을 붙일 때 주입.
    """

    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__(base_url=base_url, timeout=TIMEOUT_SECONDS, transport=transport)

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
