"""DB 엔진 지연 초기화를 실제 DB 연결 없이 검증한다."""

import pytest

from app import config, database


def _settings(database_url: str) -> config.Settings:
    return config.Settings(
        api_key="test-key",
        base_url="https://mlapi.run/example/v1",
        model="openai/gpt-4.1-mini",
        embedding_model="openai/text-embedding-3-small",
        data_go_kr_key="test-data-key",
        safetykorea_key="test-safety-key",
        law_oc="test-oc",
        database_url=database_url,
    )


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    """테스트마다 엔진·세션 팩토리 캐시를 비워, 앞 테스트의 엔진이 남지 않게 한다."""
    database.get_engine.cache_clear()
    database.get_session_factory.cache_clear()
    yield
    database.get_engine.cache_clear()
    database.get_session_factory.cache_clear()


def _use(monkeypatch, database_url: str) -> None:
    monkeypatch.setattr(database, "get_settings", lambda: _settings(database_url))


def test_DATABASE_URL이_비어_있으면_DB_미설정_예외를_낸다(monkeypatch):
    # 개발 단계에서 의도적으로 비워둔 상태라, 설정 오류와 구분되는 전용 예외여야 한다.
    _use(monkeypatch, "")

    with pytest.raises(database.DatabaseNotConfiguredError):
        database.get_engine()


def test_엔진을_만들_수_없는_접속_문자열은_설정_오류로_알리고_비밀번호는_노출하지_않는다(monkeypatch):
    # 드라이버가 없는 URL은 기다려도 풀리지 않는 설정·배포 오류다.
    _use(monkeypatch, "postgresql+nosuchdriver://ai:secret-password@db:5432/ai")

    with pytest.raises(config.ConfigError) as exc_info:
        database.get_engine()

    assert not isinstance(exc_info.value, database.DatabaseNotConfiguredError)
    assert "secret-password" not in str(exc_info.value)


def test_엔진은_한_번_만들어_재사용하고_연결은_하지_않는다(monkeypatch):
    # 닿지 않는 주소여도 엔진 생성은 성공해야 한다. 연결은 실제로 쓸 때 일어난다.
    _use(monkeypatch, "postgresql+psycopg://ai:ai@10.255.255.1:5432/ai")

    engine = database.get_engine()

    assert database.get_engine() is engine
    assert engine.url.host == "10.255.255.1"


def test_세션_팩토리는_공용_엔진에_묶인다(monkeypatch):
    _use(monkeypatch, "postgresql+psycopg://ai:ai@localhost:5433/ai")

    session = database.get_session_factory()()
    try:
        assert session.get_bind() is database.get_engine()
    finally:
        session.close()
