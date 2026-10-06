"""모든 ORM 모델에 공통으로 적용되는 규칙을 DB 없이 검증한다."""

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base

TABLES = list(Base.metadata.sorted_tables)

# text-embedding-3-small 출력 차원 (utils/embedding.py)
EMBEDDING_DIM = 1536


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
def test_PostgreSQL_DDL을_만들_수_있다(table):
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))

    assert ddl.startswith(f"\nCREATE TABLE {table.name}")


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
def test_모든_테이블은_수집_시각을_DB가_채운다(table):
    fetched_at = table.c.fetched_at

    assert fetched_at.nullable is False
    assert fetched_at.server_default is not None


def test_벡터_컬럼은_임베딩_모델과_같은_차원이다():
    vector_columns = [
        column for table in TABLES for column in table.columns if isinstance(column.type, Vector)
    ]

    assert vector_columns
    assert all(column.type.dim == EMBEDDING_DIM for column in vector_columns)
