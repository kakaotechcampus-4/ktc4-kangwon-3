"""공통 ML API 설정 테스트. 실제 네트워크 요청은 보내지 않는다."""

import langchain_openai
import pytest

from app import config


def test_api_key가_없으면_설정_로딩에_실패한다(monkeypatch):
    """환경과 .env 어디에도 API 키가 없으면 호출 전에 실패한다."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda **kwargs: False)

    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        config.load_settings()


def test_허용되지_않은_모델은_거부한다():
    with pytest.raises(config.ConfigError, match="허용되지 않은 모델"):
        config.Settings(api_key="test-key", model="openai/gpt-4.1")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://mlapi.run/example/v1",
        "https://mlapi.run/example/v2",
        "",
    ],
)
def test_잘못된_base_url은_거부한다(base_url):
    with pytest.raises(config.ConfigError, match="Base URL"):
        config.Settings(api_key="test-key", base_url=base_url)


def test_build_chat_model이_설정값을_chatopenai에_전달한다(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fake_chat_openai)
    settings = config.Settings(
        api_key="test-key",
        base_url="https://mlapi.run/example/v1",
        model="openai/gpt-4.1-mini",
    )

    result = config.build_chat_model(settings)

    assert result is sentinel
    assert captured == {
        "model": settings.model,
        "base_url": settings.base_url,
        "api_key": settings.api_key,
        "temperature": 0,
        "timeout": config.TIMEOUT_SECONDS,
        "max_retries": config.MAX_RETRIES,
    }
