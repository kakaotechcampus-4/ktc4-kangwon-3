"""에이전트 공통 Base 테스트. 가짜 하위 에이전트와 가짜 모델로 실제 API 없이 확인한다."""

import logging
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app import prompts
from app.agents.base import AgentError, AgentFailure, AgentSpec, BaseAgent

_USAGE = {
    "input_tokens": 3000,
    "output_tokens": 300,
    "total_tokens": 3300,
    "input_token_details": {"cache_read": 1000},
}


class _Answer(BaseModel):
    text: str


class _FakeError(AgentError):
    pass


class _FakeAgent(BaseAgent[_Answer]):
    spec = AgentSpec(
        name="fake",
        prompt="selection",
        output=_Answer,
        error=_FakeError,
        call_failed_message="가짜 호출에 실패했습니다: {exc}",
        parse_failed_message="모델 응답이 _Answer 스키마와 맞지 않습니다: {error}",
    )

    def answer(self, question: str, *, partial_result=None) -> _Answer:
        return self._invoke(question, subject_id="P001", partial_result=partial_result)


class _StrictAgent(_FakeAgent):
    spec = AgentSpec(
        name="strict",
        prompt="verification",
        output=_Answer,
        error=_FakeError,
        call_failed_message="{exc_type}: {exc}",
        parse_failed_message="{error}",
        strict=True,
        requires_model=False,
    )


class _StubModel:
    """with_structured_output(...).invoke(messages)만 흉내 낸다."""

    model_name = "openai/gpt-4.1-mini"

    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.options: dict = {}
        self.messages: list = []

    def with_structured_output(self, schema, **kwargs):
        self.options = {"schema": schema, **kwargs}
        return self

    def invoke(self, messages):
        self.messages = messages
        if self._error is not None:
            raise self._error
        return self._result


def _raw():
    return SimpleNamespace(usage_metadata=_USAGE, response_metadata={"model_name": "gpt-4.1-mini"})


def _ok(text="답"):
    return {"raw": _raw(), "parsed": _Answer(text=text), "parsing_error": None}


@pytest.fixture
def records(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.usage.record",
        lambda name, measured, **kwargs: calls.append({"name": name, "usage": measured, **kwargs}),
    )
    return calls


def test_성공하면_파싱_결과를_돌려주고_사용량을_한_번_기록한다(records):
    agent = _FakeAgent(_StubModel(_ok("안녕")))

    assert agent.answer("질문") == _Answer(text="안녕")
    assert len(records) == 1
    assert records[0]["name"] == "fake"
    assert records[0]["ok"] is True
    assert records[0]["subject_id"] == "P001"
    assert records[0]["configured_model"] == "openai/gpt-4.1-mini"
    assert records[0]["usage"].input_tokens == 3000


def test_시스템_프롬프트와_사용자_입력으로_메시지를_만든다(records):
    model = _StubModel(_ok())

    _FakeAgent(model).answer("상품 JSON")

    system, human = model.messages
    assert system.content == prompts.load_prompt("selection")
    assert human.content == "상품 JSON"


def test_호출_실패는_에이전트_예외로_바꾸고_원인을_보존한다(records):
    cause = TimeoutError("timeout")

    with pytest.raises(_FakeError) as raised:
        _FakeAgent(_StubModel(error=cause)).answer("질문")

    error = raised.value
    assert isinstance(error, AgentError)
    assert str(error) == "가짜 호출에 실패했습니다: timeout"
    assert error.agent == "fake"
    assert error.failure is AgentFailure.CALL
    assert error.__cause__ is cause
    assert len(records) == 1
    assert records[0]["ok"] is False
    assert records[0]["error_type"] == "TimeoutError"
    assert records[0]["usage"] is None


def test_파싱_실패는_PARSE로_바꾸고_쓴_토큰은_기록한다(records):
    cause = ValueError("필드 누락")
    model = _StubModel({"raw": _raw(), "parsed": None, "parsing_error": cause})

    with pytest.raises(_FakeError) as raised:
        _FakeAgent(model).answer("질문")

    assert raised.value.failure is AgentFailure.PARSE
    assert raised.value.__cause__ is cause
    assert str(raised.value) == "모델 응답이 _Answer 스키마와 맞지 않습니다: 필드 누락"
    assert records[0]["error_type"] == "ValueError"
    assert records[0]["usage"].output_tokens == 300


def test_파싱_결과가_비어_있으면_MissingParsedOutput으로_기록한다(records):
    model = _StubModel({"raw": _raw(), "parsed": None, "parsing_error": None})

    with pytest.raises(_FakeError) as raised:
        _FakeAgent(model).answer("질문")

    assert raised.value.failure is AgentFailure.PARSE
    assert records[0]["error_type"] == "MissingParsedOutput"


def test_실패해도_부분_결과를_예외에_담는다(records):
    partial = {"rules": "완료"}

    with pytest.raises(_FakeError) as raised:
        _FakeAgent(_StubModel(error=RuntimeError("x"))).answer("질문", partial_result=partial)

    assert raised.value.partial_result is partial


def test_구조화_출력은_원본_응답을_함께_받는다(records):
    model = _StubModel(_ok())

    _FakeAgent(model)

    assert model.options == {"schema": _Answer, "include_raw": True}


def test_strict_설정이면_json_schema_strict로_요청한다(records):
    model = _StubModel(_ok())

    _StrictAgent(model)

    assert model.options == {"schema": _Answer, "include_raw": True, "method": "json_schema", "strict": True}


def test_모델이_필수면_주입이_없을_때_공용_설정으로_만든다(monkeypatch, records):
    built = _StubModel(_ok())
    monkeypatch.setattr("app.agents.base.build_chat_model", lambda: built)

    agent = _FakeAgent()

    assert agent.answer("질문") == _Answer(text="답")


def test_모델이_필수가_아니면_모델_없이_만들고_호출은_실패한다(monkeypatch, records):
    monkeypatch.setattr("app.agents.base.build_chat_model", lambda: pytest.fail("모델을 만들면 안 됨"))
    agent = _StrictAgent()

    with pytest.raises(_FakeError) as raised:
        agent.answer("질문", partial_result="규칙 결과")

    assert raised.value.failure is None
    assert raised.value.partial_result == "규칙 결과"
    assert records == []


def test_사용량_로그_이름과_설정_모델을_바꿀_수_있다(records):
    agent = _FakeAgent(_StubModel(_ok()), configured_model="custom", usage_agent="fake-eval")

    agent.answer("질문")

    assert records[0]["name"] == "fake-eval"
    assert records[0]["configured_model"] == "custom"


def test_프롬프트_지문은_모델에_보내는_시스템_프롬프트로_계산한다(records):
    model = _StubModel(_ok())
    agent = _FakeAgent(model)

    agent.answer("질문")

    assert agent.prompt_version == prompts.fingerprint_text(model.messages[0].content)


def test_토큰_로그는_에이전트_모듈_로거로_남긴다(records, caplog):
    with caplog.at_level(logging.INFO, logger=_FakeAgent.__module__):
        _FakeAgent(_StubModel(_ok())).answer("질문")

    assert any(r.name == _FakeAgent.__module__ and "fake 토큰 사용량" in r.message for r in caplog.records)


def test_spec이_없으면_클래스를_정의할_때_실패한다():
    with pytest.raises(TypeError, match="AgentSpec"):

        class _NoSpec(BaseAgent[_Answer]):
            pass


def test_spec의_예외가_AgentError_하위가_아니면_실패한다():
    with pytest.raises(TypeError, match="AgentError"):
        AgentSpec(
            name="bad",
            prompt="selection",
            output=_Answer,
            error=RuntimeError,
            call_failed_message="",
            parse_failed_message="",
        )
