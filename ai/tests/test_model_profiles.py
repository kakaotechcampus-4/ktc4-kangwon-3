"""모델 카탈로그·프로필 구성 규칙을 확인한다."""

import pytest

from app import usage
from app.config import AGENT_PROFILES, CHAT_MODELS, MODEL_PROFILES, ChatModel, ModelProfile, Price

_REASONING = ChatModel("openai/reasoning", None, reasoning_efforts=("low", "medium"))


def test_추론_모델에_temperature를_주면_만들_때_실패한다():
    with pytest.raises(ValueError, match="temperature"):
        ModelProfile("wrong", _REASONING, temperature=0)


def test_모델이_받지_않는_추론_강도는_거부한다():
    with pytest.raises(ValueError, match="추론 강도"):
        ModelProfile("wrong", _REASONING, reasoning_effort="xhigh")
    with pytest.raises(ValueError, match="추론 강도"):
        ModelProfile("wrong", ChatModel("openai/plain", None), reasoning_effort="low")


def test_기본_배정은_있는_프로필만_가리키고_프로필_모델은_카탈로그에_있다():
    assert set(AGENT_PROFILES.values()) <= set(MODEL_PROFILES)
    for name, profile in MODEL_PROFILES.items():
        assert profile.name == name
        assert CHAT_MODELS[profile.model.id] is profile.model


def test_메타데이터에_프로필_모델_조건_단가를_남긴다():
    model = ChatModel("openai/plain", Price(1, 0.5, 2), price_source="테스트")

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
    assert "openai/gpt-4.1-mini" in usage.PRICING_KRW
