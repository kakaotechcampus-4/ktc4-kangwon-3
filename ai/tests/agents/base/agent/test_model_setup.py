"""BaseAgent 모델 준비: 구조화 출력 옵션, 모델 미주입 시 프로필로 생성 (#284, #311), 호출별 출력 스키마 (#742)."""

from typing import Literal

import pytest
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel


def test_include_raw로_구조화_출력을_만들고_에이전트별_옵션을_더한다(fakes, stub_model):
    plain, strict = stub_model(), stub_model()

    fakes.Agent(plain)
    fakes.Strict(strict)

    assert plain.structured_calls == [(fakes.answer_format, {"include_raw": True})]
    assert strict.structured_calls == [
        (fakes.answer_format, {"include_raw": True, "method": "json_schema", "strict": True}),
    ]


def test_모델을_주입하지_않으면_에이전트_프로필로_만든다(fakes, stub_model, monkeypatch):
    model = stub_model()
    names: list[str] = []
    monkeypatch.setattr("app.agents.base.agent.build_agent_model", lambda name: names.append(name) or model)

    fakes.Agent()

    # component_name으로 AGENT_PROFILES의 프로필을 고름
    assert names == ["fake"]
    assert model.structured_calls == [(fakes.answer_format, {"include_raw": True})]


def test_Tool_안_에이전트는_Tool_프로필로_모델을_만든다(fakes, stub_model, monkeypatch):
    names: list[str] = []
    monkeypatch.setattr("app.agents.base.agent.build_agent_model", lambda name: pytest.fail("에이전트 표를 쓰면 안 됨"))
    monkeypatch.setattr("app.agents.base.agent.build_tool_model", lambda name: names.append(name) or stub_model())

    class _ToolReviewer(fakes.Agent):
        model_profile = ("tool", "labeling_advertising_detection")

    _ToolReviewer()

    assert names == ["labeling_advertising_detection"]


def test_자동_생성을_끈_에이전트는_모델_없이_만들고_호출은_막는다(fakes, monkeypatch):
    monkeypatch.setattr("app.agents.base.agent.build_agent_model", lambda name: pytest.fail("모델을 만들면 안 됨"))
    agent = fakes.RulesOnly()

    with pytest.raises(RuntimeError, match="모델 없이"):
        agent.run(fakes.question)


class _Narrow(BaseModel):
    # 입력마다 허용 값을 좁힌 스키마 예시 (검증 에이전트의 판단 ID 제한)
    value: Literal["a"]


def test_호출에_스키마를_주면_그_스키마로_감싸_호출하고_파싱한다(fakes, stub_model):
    model = stub_model({"value": "a"})
    agent = fakes.Strict(model)

    output, _, _ = agent._call_model(agent._build_messages(fakes.question), subject_id="p-1", output_schema=_Narrow)

    assert isinstance(output, _Narrow)
    # 생성 때 기본 스키마 한 번, 호출 때 받은 스키마 한 번. 옵션은 같음
    narrow_format = type_to_response_format_param(_Narrow)["json_schema"]
    assert model.structured_calls[1] == (narrow_format, {"include_raw": True, "method": "json_schema", "strict": True})


def test_호출에_준_스키마를_벗어난_출력은_파싱_실패다(fakes, stub_model, records):
    agent = fakes.Agent(stub_model({"value": "b"}))

    with pytest.raises(fakes.Error) as caught:
        agent._call_model(agent._build_messages(fakes.question), subject_id="p-1", output_schema=_Narrow)

    assert caught.value.meta.failure_phase == "parsing"


def test_스키마를_주지_않으면_생성_때_감싼_호출을_그대로_쓴다(fakes, stub_model):
    model = stub_model({"value": "b"})
    agent = fakes.Agent(model)

    output, _, _ = agent._call_model(agent._build_messages(fakes.question), subject_id="p-1")

    assert output == fakes.Answer(value="b")
    assert len(model.structured_calls) == 1
