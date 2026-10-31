"""판단 프로필의 모델 회사에 맞는 판단 클라이언트를 만드는지 확인한다. 실제 API는 호출하지 않는다."""

import pytest

from app import config
from app.clients.llm import decision
from app.clients.llm.decision import (OpenAIDecisionClient, TypeSafeDecisionClient, build_decision_client,
                                      close_decision_clients, get_decision_client)
from app.config.catalog import DecisionModel

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


@pytest.mark.parametrize(("profile_name", "client_class"), [
    ("jev", TypeSafeDecisionClient),
    ("luna", OpenAIDecisionClient),
])
def test_모델_회사에_맞는_형식의_클라이언트를_게이트웨이_주소_키로_만든다(profile_name, client_class):
    client = build_decision_client(config.DECISION_PROFILES[profile_name], _SETTINGS)

    try:
        assert type(client) is client_class
        assert str(client._client.base_url) == "https://mlapi.run/example/v1/"
        assert client._client.headers["Authorization"] == "Bearer test-key"
    finally:
        client.close()


def test_형식을_모르는_모델_회사는_ConfigError():
    profile = config.DecisionProfile("unknown", DecisionModel("model", "unknown-vendor", None))

    with pytest.raises(config.ConfigError, match="unknown-vendor/model"):
        build_decision_client(profile, _SETTINGS)


def test_카탈로그의_판단_모델은_모두_형식이_있다():
    for model in config.DECISION_MODELS.values():
        client = build_decision_client(config.DecisionProfile("check", model), _SETTINGS)
        client.close()


@pytest.fixture
def shared(monkeypatch):
    """공유 클라이언트를 테스트 설정으로 만들고 끝나면 닫음."""
    monkeypatch.setattr(decision, "load_settings", lambda: _SETTINGS)
    yield
    close_decision_clients()


def test_공유_클라이언트는_같은_형식이면_하나를_다시_쓴다(shared):
    jev = config.DECISION_PROFILES["jev"]

    first = get_decision_client(jev)

    assert get_decision_client(jev) is first
    assert get_decision_client(config.DECISION_PROFILES["luna"]) is not first


def test_공유_클라이언트를_닫으면_다음엔_새로_만든다(shared):
    jev = config.DECISION_PROFILES["jev"]
    first = get_decision_client(jev)

    close_decision_clients()

    assert first._client.is_closed
    assert get_decision_client(jev) is not first
