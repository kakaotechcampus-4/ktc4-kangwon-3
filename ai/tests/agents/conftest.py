"""에이전트 테스트 공용 설정.

- stub_model: 응답을 정해 두는 가짜 모델 (구조화 출력 인자·받은 메시지 기록)
- records: 사용량 기록(app.agents.base.record) 캡처
- fake_gateway: 실제 ChatOpenAI에 붙이는 가짜 스트리밍 게이트웨이 (네트워크로 나가지 않음)
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

FakeGateway = Callable[..., ChatOpenAI]


class StubModel:
    """정해 둔 응답을 돌려주고 받은 인자를 기록하는 모델.

    Attributes:
        structured_calls: ``with_structured_output``에 넘어온 (스키마, 옵션) 목록.
        received: ``invoke``에 넘어온 메시지 목록.
    """

    model_name = "openai/gpt-4.1-mini"

    def __init__(
        self,
        reply: BaseModel | dict[str, Any] | str | None = None,
        *,
        error: Exception | None = None,
        result: dict[str, Any] | None = None,
        usage: tuple[int, int, int] = (100, 40, 20),
    ) -> None:
        """가짜 모델을 만든다.

        Args:
            reply: 응답 본문. 모델·dict는 JSON으로 바꾸고, 문자열은 그대로(잘린 JSON 등). None이면 빈 본문.
            error: 호출 때 던질 예외. 주면 응답 대신 던짐.
            result: ``invoke`` 결과 전체. 주면 reply·usage는 안 씀 (parsed·parsing_error·거절 같은 특수 응답).
            usage: (입력, 캐시 읽기, 출력) 토큰.
        """
        if isinstance(reply, BaseModel):
            reply = reply.model_dump_json()
        elif isinstance(reply, dict):
            reply = json.dumps(reply, ensure_ascii=False)
        self._content = reply or ""
        self._error = error
        self._result = result
        self._usage = usage
        self.structured_calls: list[tuple[Any, dict[str, Any]]] = []
        self.received: list[list[Any]] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "StubModel":
        """구조화 출력 인자를 기록하고 자신을 돌려준다.

        Args:
            schema: 출력 JSON 스키마.
            **kwargs: include_raw·strict 등 옵션.

        Returns:
            StubModel: 자기 자신.
        """
        self.structured_calls.append((schema, kwargs))
        return self

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        """메시지를 기록하고 정해 둔 응답을 돌려준다.

        Args:
            messages: 모델에 보낸 메시지.

        Returns:
            dict[str, Any]: ``{"raw", "parsed", "parsing_error"}``.

        Raises:
            Exception: ``error``를 준 경우 그 예외.
        """
        self.received.append(messages)
        if self._error is not None:
            raise self._error
        if self._result is not None:
            return self._result
        input_tokens, cached, output = self._usage
        raw = AIMessage(
            content=self._content,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output,
                "total_tokens": input_tokens + output,
                "input_token_details": {"cache_read": cached},
            },
            response_metadata={"model_name": self.model_name},
        )
        return {"raw": raw, "parsed": None, "parsing_error": None}


@pytest.fixture
def stub_model() -> type[StubModel]:
    """가짜 모델 클래스. ``stub_model(reply)``·``stub_model(error=...)``로 만든다."""
    return StubModel


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """에이전트가 남긴 사용량 기록 행. 키는 agent·usage와 record 키워드 인자(subject_id·ok·error_type 등)."""
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.agents.base.record",
        lambda agent, usage, **kwargs: captured.append({"agent": agent, "usage": usage, **kwargs}),
    )
    return captured


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
