"""BaseAgent의 모델 호출 순서·사용량 기록·예외 변환(#171 §4.2·§4.4)을 가짜 에이전트로 확인한다."""

import json
import logging

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel, ValidationError

from app.agents.base import AgentError, BaseAgent, MissingParsedOutput, ModelFailurePhase
from app.prompts import PromptName, get_prompt


class _Answer(BaseModel):
    value: str


# SDK가 Pydantic 클래스를 변환할 때와 같은 dict 스키마의 json_schema 부분
_ANSWER_FORMAT = type_to_response_format_param(_Answer)["json_schema"]


class _FakeError(AgentError):
    pass


class _FakeAgent(BaseAgent[_Answer]):
    component_name = "fake"
    prompt_name = PromptName.EXTRACTION
    output_schema = _Answer
    error_class = _FakeError

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        return f"{phase.value} 실패"


class _StrictFakeAgent(_FakeAgent):
    structured_output_options = {"method": "json_schema", "strict": True}


class _RulesOnlyFakeAgent(_FakeAgent):
    creates_default_model = False


def _raw(input_tokens: int = 100, cached: int = 40, output: int = 20) -> AIMessage:
    return AIMessage(
        content="",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output,
            "total_tokens": input_tokens + output,
            "input_token_details": {"cache_read": cached},
        },
        response_metadata={"model_name": "openai/gpt-4.1-mini", "token_usage": {"prompt_tokens": input_tokens}},
    )


class _StubModel:
    """with_structured_output 인자를 기록하고 정해진 결과를 돌려주는 모델."""

    model_name = "openai/gpt-4.1-mini"

    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.structured_calls: list[tuple[type, dict]] = []
        self.received: list[list] = []

    def with_structured_output(self, schema: type, **kwargs):
        self.structured_calls.append((schema, kwargs))
        return self

    def invoke(self, messages: list) -> dict:
        self.received.append(messages)
        if self._error is not None:
            raise self._error
        return self._result


@pytest.fixture
def records(monkeypatch) -> list[dict]:
    captured: list[dict] = []
    monkeypatch.setattr(
        "app.agents.base.record",
        lambda agent, usage, **kwargs: captured.append({"agent": agent, "usage": usage, **kwargs}),
    )
    return captured


def test_include_raw로_구조화_출력을_만들고_에이전트별_옵션을_더한다():
    plain, strict = _StubModel(), _StubModel()

    _FakeAgent(plain)
    _StrictFakeAgent(strict)

    assert plain.structured_calls == [(_ANSWER_FORMAT, {"include_raw": True})]
    assert strict.structured_calls == [(_ANSWER_FORMAT, {"include_raw": True, "method": "json_schema", "strict": True})]


def test_성공하면_파싱_결과를_돌려주고_사용량을_한_번_기록한다(records):
    answer = _Answer(value="ok")
    model = _StubModel({"raw": _raw(), "parsed": answer, "parsing_error": None})

    result = _FakeAgent(model)._invoke(["msg"], subject_id="p-1")

    assert result is answer
    assert model.received == [["msg"]]
    assert len(records) == 1
    row = records[0]
    assert (row["agent"], row["subject_id"], row["ok"], row["error_type"]) == ("fake", "p-1", True, None)
    assert row["configured_model"] == "openai/gpt-4.1-mini"
    assert (row["usage"].input_tokens, row["usage"].cached_tokens, row["usage"].output_tokens) == (100, 40, 20)


def test_호출이_실패하면_사용량_없이_기록하고_CALL_예외로_감싼다(records):
    cause = TimeoutError("게이트웨이 응답 없음")

    with pytest.raises(_FakeError, match="call 실패") as caught:
        _FakeAgent(_StubModel(error=cause))._invoke(["msg"], subject_id="p-1", partial_result={"rules": 1})

    assert caught.value.__cause__ is cause
    assert caught.value.partial_result == {"rules": 1}
    assert len(records) == 1
    assert (records[0]["usage"], records[0]["ok"], records[0]["error_type"]) == (None, False, "TimeoutError")


def test_파싱_오류는_사용량을_보존하고_PARSING_예외로_감싼다(records):
    cause = ValueError("스키마 불일치")
    model = _StubModel({"raw": _raw(), "parsed": None, "parsing_error": cause})

    with pytest.raises(_FakeError, match="parsing 실패") as caught:
        _FakeAgent(model)._invoke(["msg"], subject_id="p-1")

    assert caught.value.__cause__ is cause
    assert len(records) == 1
    assert (records[0]["ok"], records[0]["error_type"]) == (False, "ValueError")
    assert records[0]["usage"].input_tokens == 100


def test_파싱_결과가_비면_MissingParsedOutput을_원인으로_연결한다(records):
    model = _StubModel({"raw": _raw(), "parsed": None, "parsing_error": None})

    with pytest.raises(_FakeError, match="parsing 실패") as caught:
        _FakeAgent(model)._invoke(["msg"], subject_id="p-1")

    assert isinstance(caught.value.__cause__, MissingParsedOutput)
    assert (len(records), records[0]["error_type"]) == (1, "MissingParsedOutput")


def test_dict_출력은_출력_스키마로_검증해_돌려준다(records):
    model = _StubModel({"raw": _raw(), "parsed": {"value": "ok"}, "parsing_error": None})

    result = _FakeAgent(model)._invoke([], subject_id="p-1")

    assert result == _Answer(value="ok")
    assert records[0]["ok"] is True


def test_스키마_검증에_실패해도_토큰을_기록하고_PARSING으로_감싼다(records):
    model = _StubModel({"raw": _raw(), "parsed": {"wrong": 1}, "parsing_error": None})

    with pytest.raises(_FakeError, match="parsing 실패") as caught:
        _FakeAgent(model)._invoke([], subject_id="p-1")

    assert isinstance(caught.value.__cause__, ValidationError)
    assert len(records) == 1
    assert (records[0]["ok"], records[0]["error_type"], records[0]["usage"].input_tokens) == (False, "ValidationError", 100)


def test_에이전트_예외는_AgentError와_RuntimeError로도_잡힌다(records):
    with pytest.raises(AgentError):
        _FakeAgent(_StubModel(error=RuntimeError("x")))._invoke([], subject_id="p-1")
    with pytest.raises(RuntimeError):
        _FakeAgent(_StubModel(error=RuntimeError("x")))._invoke([], subject_id="p-1")


def test_usage_agent를_넘기면_그_이름으로_기록한다(records):
    model = _StubModel({"raw": _raw(), "parsed": _Answer(value="ok"), "parsing_error": None})

    _FakeAgent(model, usage_agent="fake-eval", configured_model="custom")._invoke([], subject_id="p-1")

    assert (records[0]["agent"], records[0]["configured_model"]) == ("fake-eval", "custom")


def test_모델을_주입하지_않으면_공통_설정의_build_chat_model로_만든다(monkeypatch):
    model = _StubModel()
    monkeypatch.setattr("app.agents.base.build_chat_model", lambda: model)

    _FakeAgent()

    assert model.structured_calls == [(_ANSWER_FORMAT, {"include_raw": True})]


def test_자동_생성을_끈_에이전트는_모델_없이_만들고_호출은_막는다(monkeypatch):
    monkeypatch.setattr("app.agents.base.build_chat_model", lambda: pytest.fail("모델을 만들면 안 됨"))
    agent = _RulesOnlyFakeAgent()

    with pytest.raises(RuntimeError, match="모델 없이"):
        agent._invoke([], subject_id="p-1")


def test_성공하면_수집한_사용량으로_콘솔_로그를_남긴다(records, caplog):
    model = _StubModel({"raw": _raw(), "parsed": _Answer(value="ok"), "parsing_error": None})

    with caplog.at_level(logging.DEBUG, logger="app.agents.base"):
        _FakeAgent(model)._invoke([], subject_id="p-1")

    assert "fake 토큰 사용량 input=100 (cache_read=40) output=20 total=120" in caplog.text
    assert "게이트웨이 원본 usage" in caplog.text


def test_콘솔_로그가_실패해도_결과는_그대로다(records, monkeypatch):
    answer = _Answer(value="ok")
    model = _StubModel({"raw": _raw(), "parsed": answer, "parsing_error": None})

    def broken(*args, **kwargs):
        raise OSError("로그 핸들러 오류")

    monkeypatch.setattr("app.agents.base.logger.info", broken)

    assert _FakeAgent(model)._invoke([], subject_id="p-1") is answer
    assert len(records) == 1


def test_프롬프트는_공용_로더의_스냅샷을_쓴다():
    assert _RulesOnlyFakeAgent().prompt is get_prompt(PromptName.EXTRACTION)


def test_메시지는_시스템_프롬프트와_사용자_입력으로_만든다():
    content = [{"type": "text", "text": "상품 설명"}]

    messages = _RulesOnlyFakeAgent()._messages(content)

    assert [type(message) for message in messages] == [SystemMessage, HumanMessage]
    assert messages[0].content == get_prompt(PromptName.EXTRACTION).text
    assert messages[1].content == content


# ---------- 실제 ChatOpenAI + 가짜 게이트웨이 (스트리밍) ----------


def _gateway(content: str, finish: str, requests: list[dict]) -> ChatOpenAI:
    """스트리밍 응답을 돌려주는 가짜 게이트웨이에 붙은 실제 ChatOpenAI. 네트워크로 나가지 않음."""

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        base = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "gpt-4.1-mini"}
        chunks = [
            {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]},
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


def test_실제_모델에서도_SDK와_같은_response_format을_보낸다(records):
    requests: list[dict] = []

    result = _StrictFakeAgent(_gateway('{"value": "ok"}', "stop", requests))._invoke(
        [HumanMessage(content="x")], subject_id="p-1",
    )

    assert result == _Answer(value="ok")
    # Pydantic 클래스를 넘겼을 때 SDK가 만드는 것과 같은 요청
    assert requests[0]["response_format"] == type_to_response_format_param(_Answer)
    assert (records[0]["ok"], records[0]["usage"].input_tokens) == (True, 1000)


@pytest.mark.parametrize(
    ("content", "finish", "cause"),
    [
        ("이건 JSON이 아님", "stop", "OutputParserException"),
        ('{"wrong": 1}', "stop", "ValidationError"),
        ('{"value": "잘린', "length", "LengthFinishReasonError"),
        ('{"value": "ok"}', "content_filter", "ContentFilterFinishReasonError"),
    ],
)
def test_스트리밍_출력이_틀려도_토큰을_기록하고_PARSING으로_감싼다(records, content, finish, cause):
    requests: list[dict] = []

    with pytest.raises(_FakeError, match="parsing 실패") as caught:
        _FakeAgent(_gateway(content, finish, requests))._invoke([HumanMessage(content="x")], subject_id="p-1")

    assert type(caught.value.__cause__).__name__ == cause
    assert len(requests) == 1
    assert len(records) == 1
    assert (records[0]["ok"], records[0]["error_type"]) == (False, cause)
    assert (records[0]["usage"].input_tokens, records[0]["usage"].output_tokens) == (1000, 100)
