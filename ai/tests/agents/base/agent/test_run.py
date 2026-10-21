"""BaseAgent 실행 흐름: run·run_with_meta, _skip·_finalize 훅, 필수 메서드, 프롬프트·메시지 조립."""

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.prompts import PromptName, get_prompt


def test_run은_모델_출력을_finalize해서_돌려준다(fakes, stub_model, records):
    model = stub_model(fakes.Answer(value="ok"))

    assert fakes.Agent(model).run(fakes.question) == "OK"
    assert len(model.received) == 1


def test_run_with_meta는_결과와_호출_실행_정보를_함께_돌려준다(fakes, stub_model, records):
    outcome = fakes.Agent(stub_model(fakes.Answer(value="ok"))).run_with_meta(fakes.question)

    assert outcome.result == "OK"
    meta = outcome.meta
    assert (meta.component, meta.model, meta.error_type) == ("fake", "openai/gpt-4.1-mini", None)
    assert (meta.prompt_name, meta.prompt_sha256) == ("extraction", get_prompt(PromptName.EXTRACTION).sha256)
    assert meta.usage.input_tokens == 100
    assert meta.cost_krw is not None


def test_skip이_결과를_정하면_모델을_부르지_않고_사용량_없는_실행_정보를_돌려준다(fakes, stub_model, records):
    model = stub_model(fakes.Answer(value="ok"))

    outcome = fakes.Skipping(model).run_with_meta(fakes.Question(product_id="p-1", text=""))

    assert outcome.result == "건너뜀"
    assert model.received == []
    assert records == []
    assert (outcome.meta.usage, outcome.meta.elapsed_ms, outcome.meta.error_type) == (None, 0, None)


def test_메시지_만들기와_기록_대상을_빠뜨린_에이전트는_만들_수_없다(fakes, stub_model):
    class _Incomplete(BaseAgent):
        component_name = "incomplete"
        prompt_name = PromptName.EXTRACTION
        output_schema = fakes.Answer
        error_class = fakes.Error

    with pytest.raises(TypeError, match="_build_messages|_subject_id"):
        _Incomplete(stub_model())


def test_프롬프트는_공용_로더의_스냅샷을_쓴다(fakes):
    assert fakes.RulesOnly().prompt is get_prompt(PromptName.EXTRACTION)


def test_메시지는_시스템_프롬프트와_사용자_입력으로_만든다(fakes):
    content = [{"type": "text", "text": "상품 설명"}]

    messages = fakes.RulesOnly()._messages(content)

    assert [type(message) for message in messages] == [SystemMessage, HumanMessage]
    assert messages[0].content == get_prompt(PromptName.EXTRACTION).text
    assert messages[1].content == content
