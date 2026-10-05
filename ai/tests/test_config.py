"""AI 서버 공통 설정 테스트. 실제 네트워크 요청은 보내지 않는다."""

import langchain_openai
import pytest

from app import config

_VALID = {
    "api_key": "test-key",
    "base_url": "https://mlapi.run/example/v1",
    "model": "openai/gpt-4.1-mini",
    "embedding_model": "openai/text-embedding-3-small",
    "database_url": "postgresql+psycopg://ai:ai@localhost:5433/ai",
    "data_go_kr_key": "test-data-key",
    "safetykorea_key": "test-safety-key",
    "law_oc": "test-oc",
}

_VALID_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://mlapi.run/example/v1",
    "OPENAI_MODEL": "openai/gpt-4.1-mini",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATABASE_URL": "postgresql+psycopg://ai:ai@localhost:5433/ai",
    "DATA_GO_KR_KEY": "test-data-key",
    "KEY_SAFETYKOREA": "test-safety-key",
    "LAW_GO_KR_OC": "test-oc",
}


def _settings(**overrides) -> config.Settings:
    """필수 설정을 유효한 값으로 채운 Settings. 검사할 필드만 바꿔 넣는다."""
    return config.Settings(**{**_VALID, **overrides})


def _env(monkeypatch, **overrides):
    """실제 ai/.env를 읽지 않고, 필수 환경변수가 모두 있는 환경을 만든다. 값이 None이면 지운다."""
    monkeypatch.setattr(config, "load_dotenv", lambda **kwargs: False)
    for name, value in {**_VALID_ENV, **overrides}.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


@pytest.fixture(autouse=True)
def _fresh_settings_cache():
    """이 파일의 테스트마다 get_settings() 캐시를 비워, 앞 테스트의 설정이 남지 않게 한다."""
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_api_key가_없으면_설정_로딩에_실패한다(monkeypatch):
    """환경과 .env 어디에도 API 키가 없으면 호출 전에 실패한다."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda **kwargs: False)

    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        config.load_settings()


def test_허용되지_않은_모델은_거부한다():
    with pytest.raises(config.ConfigError, match="허용되지 않은 모델"):
        _settings(model="openai/gpt-4.1")


def test_base_url이_없으면_설정_로딩에_실패한다(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda **kwargs: False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    with pytest.raises(config.ConfigError, match="OPENAI_BASE_URL"):
        config.load_settings()


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
        _settings(base_url=base_url)


def test_잘못된_base_url은_오류_메시지에_노출되지_않는다():
    private_url = "https://mlapi.run/private-endpoint"

    with pytest.raises(config.ConfigError) as exc_info:
        _settings(base_url=private_url)

    assert private_url not in str(exc_info.value)


def test_api_key와_base_url은_repr에_노출되지_않는다():
    settings = _settings(
        api_key="private-api-key",
        base_url="https://mlapi.run/private-endpoint/v1",
    )

    representation = repr(settings)
    assert "private-api-key" not in representation
    assert "private-endpoint" not in representation


def test_필수_환경변수가_모두_있으면_설정을_읽는다(monkeypatch):
    _env(monkeypatch, DATA_GO_KR_KEY=" data-key-with-space ")

    settings = config.load_settings()

    assert settings.database_url == _VALID_ENV["DATABASE_URL"]
    # .env에 붙은 앞뒤 공백 때문에 키 인증이 실패하지 않도록 정리한다.
    assert settings.data_go_kr_key == "data-key-with-space"
    assert settings.safetykorea_key == _VALID_ENV["KEY_SAFETYKOREA"]
    assert settings.law_oc == _VALID_ENV["LAW_GO_KR_OC"]
    assert settings.model == _VALID_ENV["OPENAI_MODEL"]
    assert settings.embedding_model == _VALID_ENV["OPENAI_EMBEDDING_MODEL"]


@pytest.mark.parametrize(
    "missing",
    ["OPENAI_MODEL", "OPENAI_EMBEDDING_MODEL", "DATA_GO_KR_KEY", "KEY_SAFETYKOREA", "LAW_GO_KR_OC"],
)
def test_모델_이름과_외부_API_키가_없으면_설정_로딩에_실패한다(monkeypatch, missing):
    # 코드에 기본값이 없으므로 하나라도 빠지면 조용히 메워지지 않고 lifespan에서 기동이 실패해야 한다.
    _env(monkeypatch, **{missing: None})

    with pytest.raises(config.ConfigError, match=missing):
        config.load_settings()


def test_DATABASE_URL이_없어도_설정_로딩은_성공한다(monkeypatch):
    # 개발 단계에서는 DB 없이도 서버가 떠야 한다. 비어 있으면 DB 기능을 쓰지 않는다.
    _env(monkeypatch, DATABASE_URL=None)

    assert config.load_settings().database_url == ""


def test_빈_값도_없는_것으로_본다(monkeypatch):
    # .env.example처럼 "KEY=" 로 비워두거나 공백만 넣은 경우다.
    _env(monkeypatch, KEY_SAFETYKOREA="   ")

    with pytest.raises(config.ConfigError, match="KEY_SAFETYKOREA"):
        config.load_settings()


def test_빠진_필수_환경변수는_한_번에_모두_알려준다(monkeypatch):
    # 하나 고치고 다시 띄우기를 반복하지 않도록 빠진 이름을 모두 보여준다.
    _env(monkeypatch, OPENAI_API_KEY=None, DATA_GO_KR_KEY=None, LAW_GO_KR_OC=None, DATABASE_URL=None)

    with pytest.raises(config.ConfigError) as exc_info:
        config.load_settings()

    message = str(exc_info.value)
    for name in ("OPENAI_API_KEY", "DATA_GO_KR_KEY", "LAW_GO_KR_OC"):
        assert name in message
    # 있는 값과 선택 설정은 빠진 목록에 넣지 않는다.
    assert "KEY_SAFETYKOREA" not in message
    assert "DATABASE_URL" not in message


@pytest.mark.parametrize(
    "field_name", ["model", "embedding_model", "data_go_kr_key", "safetykorea_key", "law_oc"],
)
def test_Settings를_직접_만들어도_필수_값이_비면_거부한다(field_name):
    with pytest.raises(config.ConfigError, match="필수 설정이 비어 있습니다"):
        _settings(**{field_name: ""})


def test_DATABASE_URL은_비어_있으면_허용한다():
    assert _settings(database_url="").database_url == ""


def test_DB_접속_문자열이_postgresql이_아니면_거부하고_값은_노출하지_않는다():
    wrong = "mysql://ai:secret-password@db:3306/ai"

    with pytest.raises(config.ConfigError, match="DATABASE_URL") as exc_info:
        _settings(database_url=wrong)

    assert "secret-password" not in str(exc_info.value)


def test_DB_접속_정보와_외부_API_키는_repr에_노출되지_않는다():
    settings = _settings(
        database_url="postgresql+psycopg://ai:secret-password@db:5432/ai",
        data_go_kr_key="private-data-key",
        safetykorea_key="private-safety-key",
        law_oc="private-oc",
    )

    representation = repr(settings)
    for secret in ("secret-password", "private-data-key", "private-safety-key", "private-oc"):
        assert secret not in representation


def test_build_chat_model이_설정값을_chatopenai에_전달한다(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", fake_chat_openai)
    settings = _settings(model="openai/gpt-4.1-mini")

    result = config.build_chat_model(settings)

    assert result is sentinel
    assert captured == {
        "model": settings.model,
        "base_url": settings.base_url,
        "api_key": settings.api_key,
        "temperature": 0,
        "timeout": config.TIMEOUT_SECONDS,
        "max_retries": config.MAX_RETRIES,
        # 게이트웨이의 비스트리밍 출력 한도(2,000토큰)를 피한다. 빠지면 긴 페이지 추출이 실패한다.
        "streaming": True,
        "stream_usage": True,
    }


def test_get_settings는_한_번_읽은_설정을_계속_재사용한다(monkeypatch):
    _env(monkeypatch)
    first = config.get_settings()

    # 이후에 환경변수가 바뀌어도 기동 시점에 검증한 설정을 그대로 쓴다.
    monkeypatch.setenv("LAW_GO_KR_OC", "changed-oc")

    assert config.get_settings() is first
    assert config.get_settings().law_oc == _VALID_ENV["LAW_GO_KR_OC"]


def test_get_settings는_검증에_실패한_결과를_캐시하지_않는다(monkeypatch):
    # 설정을 고친 뒤 다시 호출하면 새로 읽어야 한다. 실패가 캐시되면 고쳐도 계속 실패한다.
    _env(monkeypatch, KEY_SAFETYKOREA=None)
    with pytest.raises(config.ConfigError, match="KEY_SAFETYKOREA"):
        config.get_settings()

    monkeypatch.setenv("KEY_SAFETYKOREA", "fixed-key")

    assert config.get_settings().safetykorea_key == "fixed-key"
