"""관세청 세관장확인대상물품 GW 조회 객체를 DB·네트워크 없이 검증한다."""

from datetime import timedelta

from app.clients.customs import CustomsGwClient
from app.config import CUSTOMS_GW_TTL_SECONDS
from app.db import customs_cache
from app.db.errors import DatabaseNotConfiguredError
from app.db.fetchers import OnDemandFetcher
from app.schemas.clients.customs_response import CustomsGwConfirmationResponse


def test_GW_조회_객체는_조회할_때_쌓고_하루_보관한다():
    fetcher = customs_cache.build_customs_gw_fetcher("test-key", None)

    assert isinstance(fetcher, OnDemandFetcher)
    assert isinstance(fetcher._client, CustomsGwClient)
    assert fetcher._name == "customs.gw"
    assert fetcher._response_type is CustomsGwConfirmationResponse
    assert fetcher._ttl == timedelta(seconds=CUSTOMS_GW_TTL_SECONDS) == timedelta(days=1)
    fetcher.close()


def test_Tool용_GW_조회_객체는_공용_DB_세션을_쓴다(monkeypatch):
    factory = object()
    monkeypatch.setattr(customs_cache, "get_session_factory", lambda: factory)

    fetcher = customs_cache.open_customs_gw_fetcher("test-key")

    assert fetcher._session_factory is factory
    fetcher.close()


def test_DATABASE_URL이_없으면_Tool용_GW_조회_객체는_클라이언트만_쓴다(monkeypatch):
    def not_configured():
        raise DatabaseNotConfiguredError("DATABASE_URL이 설정되지 않음")
    monkeypatch.setattr(customs_cache, "get_session_factory", not_configured)

    fetcher = customs_cache.open_customs_gw_fetcher("test-key")

    assert fetcher._session_factory is None
    fetcher.close()
