"""채팅 모델 생성 테스트. 가짜 ChatOpenAI로 바꿔 실제 API는 호출하지 않는다."""

import langchain_openai
import pytest

from app import config
from app.clients.llm import chat, close_llm_clients, get_llm_client

_SETTINGS = config.Settings(
    api_key="test-key",
    base_url="https://mlapi.run/example/v1",
    embedding_model="openai/text-embedding-3-small",
    database_url="",
    data_go_kr_key="test-data-key",
    safetykorea_key="test-safety-key",
    law_oc="test-oc",
    internal_api_token="test-internal-token-0123456789abcdef",
    be_base_url="http://be-server:8080",
)


@pytest.fixture
def captured(monkeypatch) -> dict:
    """ChatOpenAI 대신 생성 인자만 기록함."""
    kwargs_seen: dict = {}
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **kwargs: kwargs_seen.update(kwargs))
    yield kwargs_seen
    close_llm_clients()


@pytest.mark.parametrize(("profile_name", "model", "options"), [
    ("mini", "openai/gpt-4.1-mini", {"temperature": 0}),
    # 추론 모델은 temperature를 보내지 않고 추론 강도만
    ("luna-low", "openai/gpt-6-luna", {"reasoning_effort": "low"}),
])
def test_build_chat_model은_프로필에_있는_옵션만_보낸다(captured, profile_name, model, options):
    chat.build_chat_model(config.MODEL_PROFILES[profile_name], _SETTINGS)

    assert captured == {
        "model": model,
        "base_url": _SETTINGS.base_url,
        "api_key": _SETTINGS.api_key,
        **options,
        "timeout": chat.TIMEOUT_SECONDS,
        "max_retries": chat.MAX_RETRIES,
        "http_client": get_llm_client(_SETTINGS.base_url).http_client,
        # 게이트웨이의 비스트리밍 출력 한도(2,000토큰)를 피한다. 빠지면 긴 페이지 추출이 실패한다.
        "streaming": True,
        "stream_usage": True,
    }


@pytest.mark.parametrize(("build", "pick", "name"), [
    ("build_agent_model", "agent_profile", "selection"),
    ("build_tool_model", "tool_profile", "electrical_safety"),
])
def test_에이전트_Tool_모델은_설정을_한_번_읽고_프로필로_만든다(monkeypatch, captured, build, pick, name):
    reads = []
    monkeypatch.setattr(chat, "load_settings", lambda: reads.append(1) or _SETTINGS)

    getattr(chat, build)(name)

    assert len(reads) == 1
    assert captured["model"] == getattr(config, pick)(name, _SETTINGS).model.id
