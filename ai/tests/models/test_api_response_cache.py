"""외부 API 응답 캐시 모델의 제약을 DB 없이 검증한다."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.models import ApiResponseCache


def test_캐시는_클라이언트와_요청_해시_두_칸으로_찾는다():
    assert [column.name for column in ApiResponseCache.__table__.primary_key] == ["client", "request_key"]


def test_요청_해시는_sha256_16진수_길이다():
    assert ApiResponseCache.__table__.c.request_key.type.length == 64


def test_만료_시각이_없으면_영구_보관이라_비워_둘_수_있다():
    assert ApiResponseCache.__table__.c.expires_at.nullable is True
    assert ApiResponseCache.__table__.c.response.nullable is False


def test_만료_행_정리용_인덱스가_있다():
    (index,) = [index for index in ApiResponseCache.__table__.indexes
                if index.name == "ix_api_response_cache_expires_at"]

    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "ON api_response_cache (expires_at)" in sql
