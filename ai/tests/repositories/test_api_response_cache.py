"""외부 API 응답 캐시 Repository가 만드는 SQL을 DB 없이 검증한다."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import ApiResponseCache
from app.repositories.api_response_cache import ApiResponseCacheRepository


def _entry(**overrides) -> ApiResponseCache:
    fields = {
        "client": "law.text", "request_key": "a" * 64, "request": {"mst": "273575"},
        "response": {"law_id": "008044", "articles": []}, "expires_at": None,
    }
    return ApiResponseCache(**{**fields, **overrides})


def test_조회는_클라이언트와_요청_해시로_한_건을_찾는다(session):
    entry = _entry()
    session.stored[("law.text", "a" * 64)] = entry

    repo = ApiResponseCacheRepository(session)

    assert repo.get("law.text", "a" * 64) is entry
    assert repo.get("law.search", "a" * 64) is None


def test_저장은_같은_키면_응답과_수집_시각을_덮어쓴다(session):
    ApiResponseCacheRepository(session).put(_entry())

    sql = session.last_sql()
    assert sql.startswith("INSERT INTO api_response_cache")
    assert "ON CONFLICT (client, request_key) DO UPDATE SET" in sql
    assert "response = excluded.response" in sql
    assert "expires_at = excluded.expires_at" in sql
    assert "fetched_at = now()" in sql
    assert "client = excluded.client" not in sql


def test_만료_정리는_만료_시각이_지난_행만_지우고_지운_수를_돌려준다(session):
    session.execute = lambda stmt: session.statements.append(stmt) or SimpleNamespace(rowcount=3)
    now = datetime(2026, 10, 25, tzinfo=timezone.utc)

    deleted = ApiResponseCacheRepository(session).delete_expired(now)

    assert deleted == 3
    assert "DELETE FROM api_response_cache WHERE api_response_cache.expires_at < %(expires_at_1)s" in session.last_sql()
    assert session.statements[-1].compile().params["expires_at_1"] == now
