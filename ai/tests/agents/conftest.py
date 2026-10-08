"""에이전트 테스트 공용 설정. 실제 ChatOpenAI에 붙이는 가짜 스트리밍 게이트웨이."""

import json
from collections.abc import Callable

import httpx
import pytest
from langchain_openai import ChatOpenAI

FakeGateway = Callable[..., ChatOpenAI]


def make_fake_gateway(
    content: str | None,
    finish: str,
    requests: list[dict],
    *,
    refusal: str | None = None,
) -> ChatOpenAI:
    """정해진 스트리밍 응답을 돌려주는 가짜 게이트웨이에 붙은 실제 ChatOpenAI. 네트워크로 나가지 않음.

    Args:
        content: 응답 본문. None이면 본문 없음.
        finish: 종료 사유 (stop, length, content_filter).
        requests: 받은 요청 본문을 쌓을 목록.
        refusal: 모델 거절 문구.

    Returns:
        ChatOpenAI: 운영과 같은 스트리밍·사용량 설정의 모델.
    """
    delta = {"role": "assistant"}
    if content is not None:
        delta["content"] = content
    if refusal is not None:
        delta["refusal"] = refusal

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        base = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "gpt-4.1-mini"}
        chunks = [
            {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
            # 사용량은 스트림 마지막 조각으로 옴
            {**base, "choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}},
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

    return ChatOpenAI(
        model="openai/gpt-4.1-mini",
        api_key="test-key",
        base_url="https://gateway.invalid/v1",
        streaming=True,
        stream_usage=True,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


@pytest.fixture
def fake_gateway() -> FakeGateway:
    """가짜 게이트웨이 모델을 만드는 함수."""
    return make_fake_gateway
