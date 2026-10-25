"""AI 서버 공통 설정 테스트. 실제 네트워크 요청은 보내지 않는다."""

import pytest

from app import config

_VALID = {
    "api_key": "test-key",
    "base_url": "https://mlapi.run/example/v1",
    "embedding_model": "openai/text-embedding-3-small",
    "database_url": "postgresql+psycopg://ai:ai@localhost:5433/ai",
    "data_go_kr_key": "test-data-key",
    "safetykorea_key": "test-safety-key",
    "law_oc": "test-oc",
    "internal_api_token": "test-internal-token-0123456789abcdef",
    "be_base_url": "http://be-server:8080",
}

_VALID_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://mlapi.run/example/v1",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATABASE_URL": "postgresql+psycopg://ai:ai@localhost:5433/ai",
    "DATA_GO_KR_KEY": "test-data-key",
    "KEY_SAFETYKOREA": "test-safety-key",
    "LAW_GO_KR_OC": "test-oc",
    "INTERNAL_API_TOKEN": "test-internal-token-0123456789abcdef",
    "BE_BASE_URL": "http://be-server:8080",
    # 셸에 남은 덮어쓰기 값이 테스트에 섞이지 않게 기본은 지움
    "MODEL_PROFILE_OVERRIDES": None,
    "AI_DEV_API_ENABLED": None,
    "AI_DEV_API_KEY": None,
}


def _settings(**overrides) -> config.Settings:
    """필수 설정을 유효한 값으로 채운 Settings. 검사할 필드만 바꿔 넣는다."""
    return config.Settings(**{**_VALID, **overrides})


def _env(monkeypatch, **overrides):
    """실제 ai/.env를 읽지 않고, 필수 환경변수가 모두 있는 환경을 만든다. 값이 None이면 지운다."""
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
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
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)

    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        config.load_settings()


def test_base_url이_없으면_설정_로딩에_실패한다(monkeypatch):
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
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
    assert settings.embedding_model == _VALID_ENV["OPENAI_EMBEDDING_MODEL"]


@pytest.mark.parametrize(
    "missing",
    ["OPENAI_EMBEDDING_MODEL", "DATA_GO_KR_KEY", "KEY_SAFETYKOREA", "LAW_GO_KR_OC",
     "INTERNAL_API_TOKEN", "BE_BASE_URL"],
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
    "field_name",
    ["embedding_model", "data_go_kr_key", "safetykorea_key", "law_oc", "internal_api_token", "be_base_url"],
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


def test_에이전트마다_기본_프로필을_쓴다(monkeypatch):
    _env(monkeypatch)
    settings = config.load_settings()

    assert config.agent_profile("extraction", settings) is config.MODEL_PROFILES["mini"]
    assert config.agent_profile("selection", settings).name == config.AGENT_PROFILES["selection"]


def test_덮어쓰기에_적은_에이전트만_프로필이_바뀐다(monkeypatch):
    _env(monkeypatch, MODEL_PROFILE_OVERRIDES=" agent.extraction = luna-low ")
    settings = config.load_settings()

    profile = config.agent_profile("extraction", settings)

    # 적지 않은 에이전트는 코드 기본값
    assert config.agent_profile("selection", settings).name == config.AGENT_PROFILES["selection"]
    assert profile.name == "luna-low"
    assert profile.model.id == "openai/gpt-6-luna"
    # 추론 모델은 temperature를 보내지 않음
    assert profile.temperature is None
    assert profile.reasoning_effort == "low"


def test_없는_프로필_이름은_기본값으로_넘기지_않고_거부한다(monkeypatch):
    _env(monkeypatch, MODEL_PROFILE_OVERRIDES="agent.selection=gpt-5")

    with pytest.raises(config.ConfigError, match="agent.selection='gpt-5'"):
        config.load_settings()


def test_프로필이_정해지지_않은_에이전트는_거부한다():
    with pytest.raises(config.ConfigError, match="unknown"):
        config.agent_profile("unknown", _settings())


def test_Tool은_에이전트와_다른_표에서_프로필을_고른다(monkeypatch):
    # 에이전트와 Tool 이름이 겹쳐도 서로의 프로필을 바꾸지 않음
    _env(monkeypatch, MODEL_PROFILE_OVERRIDES="tool.electrical_safety=luna-low")
    settings = config.load_settings()

    assert config.tool_profile("electrical_safety", settings).name == "luna-low"
    assert set(settings.agent_profiles.values()) == {"mini"}
    with pytest.raises(config.ConfigError, match="Tool"):
        config.tool_profile("extraction", settings)


def test_없는_Tool_프로필_이름도_기동을_막는다(monkeypatch):
    _env(monkeypatch, MODEL_PROFILE_OVERRIDES="tool.electrical_safety=gpt-5")

    with pytest.raises(config.ConfigError, match="tool.electrical_safety='gpt-5'"):
        config.load_settings()


def test_덮어쓰기는_쉼표로_여러_대상을_받는다():
    overrides = config.settings.parse_profile_overrides(
        "agent.extraction=luna-low, tool.electrical_safety=luna-medium,")

    assert overrides == {("agent", "extraction"): "luna-low", ("tool", "electrical_safety"): "luna-medium"}
    assert config.settings.parse_profile_overrides("") == {}


@pytest.mark.parametrize(("raw", "message"), [
    ("extraction=luna-low", "형식"),          # 종류 없음
    ("agent.extraction", "형식"),             # 프로필 없음
    ("model.extraction=luna-low", "형식"),    # 없는 종류
    ("agent.extracton=luna-low", "extracton"),  # 표에 없는 이름 (오타)
    ("tool.extraction=luna-low", "extraction"),  # 에이전트 이름을 Tool로
])
def test_덮어쓰기_오타는_조용히_무시하지_않고_기동을_막는다(monkeypatch, raw, message):
    _env(monkeypatch, MODEL_PROFILE_OVERRIDES=raw)

    with pytest.raises(config.ConfigError, match=message):
        config.load_settings()


def test_내부_API_토큰이_BE_기준보다_짧으면_거부하고_값은_노출하지_않는다():
    short = "short-internal-token-31-chars-x"

    with pytest.raises(config.ConfigError, match="INTERNAL_API_TOKEN은 32자 이상") as exc_info:
        _settings(internal_api_token=short)

    assert short not in str(exc_info.value)
    assert _settings(internal_api_token="x" * 32).internal_api_token == "x" * 32


@pytest.mark.parametrize("be_base_url", ["be-server:8080", "ftp://be-server", "localhost:8080"])
def test_BE_주소는_http나_https로_시작해야_한다(be_base_url):
    with pytest.raises(config.ConfigError, match="BE_BASE_URL"):
        _settings(be_base_url=be_base_url)


def test_내부_API_토큰은_repr에_노출되지_않는다():
    token = "private-internal-token-0123456789abcdef"

    assert token not in repr(_settings(internal_api_token=token))


_DEV_KEY = "test-dev-api-key-0123456789abcdefgh"


def test_개발용_진단은_기본으로_꺼져_있고_키도_필요_없다(monkeypatch):
    _env(monkeypatch)

    settings = config.load_settings()

    assert (settings.dev_api_enabled, settings.dev_api_key) == (False, "")


@pytest.mark.parametrize("raw", ["true", "TRUE", " 1 ", "yes", "on"])
def test_개발용_진단을_켜면_키를_읽는다(monkeypatch, raw):
    _env(monkeypatch, AI_DEV_API_ENABLED=raw, AI_DEV_API_KEY=f" {_DEV_KEY} ")

    settings = config.load_settings()

    assert (settings.dev_api_enabled, settings.dev_api_key) == (True, _DEV_KEY)


@pytest.mark.parametrize("raw", ["false", "0", "no", "off", ""])
def test_끄는_값은_모두_꺼짐으로_읽는다(monkeypatch, raw):
    _env(monkeypatch, AI_DEV_API_ENABLED=raw)

    assert config.load_settings().dev_api_enabled is False


def test_켜기_값의_오타는_꺼짐으로_넘기지_않고_기동을_막는다(monkeypatch):
    _env(monkeypatch, AI_DEV_API_ENABLED="treu")

    with pytest.raises(config.ConfigError, match="AI_DEV_API_ENABLED"):
        config.load_settings()


@pytest.mark.parametrize("key", ["", "   ", "short-dev-key-31-characters-xxx"])
def test_개발용_진단을_켰는데_키가_없거나_짧으면_기동을_막고_값은_노출하지_않는다(key):
    with pytest.raises(config.ConfigError, match="AI_DEV_API_KEY") as exc_info:
        _settings(dev_api_enabled=True, dev_api_key=key)

    if key.strip():
        assert key not in str(exc_info.value)


def test_개발용_키가_콜백_토큰과_같으면_기동을_막는다():
    # 공유되는 개발용 키로 BE 내부 API에 가짜 결과를 넣을 수 없게
    token = _VALID["internal_api_token"]

    with pytest.raises(config.ConfigError, match="INTERNAL_API_TOKEN과 다른 값") as exc_info:
        _settings(dev_api_enabled=True, dev_api_key=token)

    assert token not in str(exc_info.value)


def test_개발용_키는_repr에_노출되지_않는다():
    assert _DEV_KEY not in repr(_settings(dev_api_enabled=True, dev_api_key=_DEV_KEY))
