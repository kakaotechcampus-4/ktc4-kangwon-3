"""모델 카탈로그·프로필 구성 규칙을 확인한다."""

import pytest

from app import usage
from app.config import AGENT_PROFILES, CHAT_MODELS, MODEL_PROFILES, TOOL_PROFILES, ModelProfile, Price
from app.config.catalog import ChatModel, ClaudeModel, GeminiModel, OpenAIModel
from app.schemas.schemas import ToolName

_REASONING = OpenAIModel("reasoning", None, reasoning_efforts=("low", "medium"))


def test_카탈로그_등록명은_회사_접두어를_붙인다():
    assert OpenAIModel("gpt-4.1-mini", None).id == "openai/gpt-4.1-mini"
    assert GeminiModel("gemini-2.5-flash", None).id == "google/gemini-2.5-flash"
    assert ClaudeModel("claude-haiku-4-5", None).id == "anthropic/claude-haiku-4-5"


def test_회사_클래스_없이는_모델을_만들지_않는다():
    with pytest.raises(TypeError, match="회사 클래스"):
        ChatModel("plain", None)


def test_OpenAI_추론_모델에_temperature를_주면_만들_때_실패한다():
    with pytest.raises(ValueError, match="temperature"):
        ModelProfile("wrong", _REASONING, temperature=0)
    # 추론 모델이 아니면 temperature를 받음
    assert ModelProfile("plain", OpenAIModel("plain", None), temperature=0).temperature == 0


def test_모델이_받지_않는_추론_강도는_거부한다():
    with pytest.raises(ValueError, match="추론 강도"):
        ModelProfile("wrong", _REASONING, reasoning_effort="xhigh")
    with pytest.raises(ValueError, match="추론 강도"):
        ModelProfile("wrong", OpenAIModel("plain", None), reasoning_effort="low")


def test_Gemini는_temperature와_추론_강도를_같이_받는다():
    gemini = GeminiModel("gemini", None, reasoning_efforts=("low",))

    profile = ModelProfile("gemini", gemini, temperature=0, reasoning_effort="low")

    assert (profile.temperature, profile.reasoning_effort) == (0, "low")


@pytest.mark.parametrize("options", [{"temperature": 0}, {"reasoning_effort": "low"}])
def test_Claude는_게이트웨이를_거치면_temperature도_추론_강도도_못_준다(options):
    # 추론 강도를 카탈로그에 적어 둬도 구조화 출력과 충돌해 거부
    claude = ClaudeModel("claude", None, reasoning_efforts=("low",))

    with pytest.raises(ValueError, match="claude:"):
        ModelProfile("claude", claude, **options)
    assert ModelProfile("claude", claude).metadata()["temperature"] is None


def test_기본_배정은_있는_프로필만_가리키고_프로필_모델은_카탈로그에_있다():
    assert set(AGENT_PROFILES.values()) <= set(MODEL_PROFILES)
    for name, profile in MODEL_PROFILES.items():
        assert profile.name == name
        assert CHAT_MODELS[profile.model.id] is profile.model


def test_메타데이터에_프로필_모델_조건_단가를_남긴다():
    model = OpenAIModel("plain", Price(1, 0.5, 2), price_source="테스트")

    assert ModelProfile("plain", model, temperature=0).metadata() == {
        "profile": "plain",
        "model": "openai/plain",
        "temperature": 0,
        "reasoning_effort": None,
        "price_krw_per_1m": {"input": 1, "cached_input": 0.5, "output": 2},
        "price_source": "테스트",
    }
    assert ModelProfile("reasoning", _REASONING, reasoning_effort="low").metadata()["price_krw_per_1m"] is None


def test_비용_단가표는_단가를_아는_모델만_카탈로그에서_만든다():
    assert usage.PRICING_KRW == {
        model.id: {"input": model.price.input, "cached_input": model.price.cached_input, "output": model.price.output}
        for model in CHAT_MODELS.values() if model.price
    }
    assert set(usage.PRICING_KRW) == {"openai/gpt-4.1-mini", "openai/gpt-6-luna"}


def test_Tool_표에_있는_이름은_ToolName_값이다():
    assert set(TOOL_PROFILES) <= {tool.value for tool in ToolName}
