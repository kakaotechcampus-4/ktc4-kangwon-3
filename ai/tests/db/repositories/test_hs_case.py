"""결정사례 Repository가 만드는 SQL을 DB 없이 검증한다."""

from types import SimpleNamespace

import pytest

from app.db.models import HsCase
from app.db.repositories.hs_case import HsCaseRepository

MODEL = "openai/text-embedding-3-small"


def test_결정사례_벡터_검색은_같은_모델의_임베딩만_코사인_거리순으로_top_k만_가져온다(session):
    HsCaseRepository(session).search_by_vector([0.1] * 1536, embedding_model=MODEL, top_k=5)

    sql = session.last_sql()
    assert "hs_cases.embedding <=> %(embedding_1)s AS distance" in sql
    assert "hs_cases.embedding IS NOT NULL AND hs_cases.embedding_model = %(embedding_model_1)s" in sql
    assert "ORDER BY hs_cases.embedding <=> %(embedding_1)s" in sql
    params = session.statements[-1].compile().params
    assert params["param_1"] == 5
    assert params["embedding_model_1"] == MODEL


def test_결정사례_벡터_검색은_차원이_다른_쿼리를_거부한다(session):
    with pytest.raises(ValueError, match="1536차원"):
        HsCaseRepository(session).search_by_vector([0.1] * 512, embedding_model=MODEL)
    assert session.statements == []


def test_결정사례는_HS_코드_앞자리가_겹치는_사례를_조회한다(session):
    HsCaseRepository(session).get_by_hs_code("8414599000")

    sql = session.last_sql()
    assert "unnest(hs_cases.hs_codes) AS code" in sql
    assert "(code LIKE %(param_1)s || '%%') OR (%(param_1)s LIKE code || '%%')" in sql


def test_문서_ID_묶음_조회는_빈_목록이면_DB를_부르지_않는다(session):
    repo = HsCaseRepository(session)

    assert repo.get_many([]) == []
    assert session.statements == []

    repo.get_many(["A1", "B2"])
    assert "WHERE hs_cases.doc_id IN" in session.last_sql()


def test_일괄_저장은_같은_문서_ID면_내용과_임베딩을_덮어쓴다(session):
    case = HsCase(doc_id="A1", hs_codes=["8414599000"], product_name="선풍기", description="탁상용",
                  decision_reason="전동기 내장", enforce_date="20240101", embedding=None, embedding_model=None)

    HsCaseRepository(session).upsert_many([case])

    sql = session.last_sql()
    assert sql.startswith("INSERT INTO hs_cases")
    assert "ON CONFLICT (doc_id) DO UPDATE SET" in sql
    assert "hs_codes = excluded.hs_codes" in sql
    assert "embedding = excluded.embedding" in sql
    assert "fetched_at = now()" in sql
    assert "doc_id = excluded.doc_id" not in sql


def test_문서_ID_묶음_삭제는_빈_목록이면_DB를_부르지_않는다(session):
    repo = HsCaseRepository(session)

    assert repo.delete_many([]) == 0
    assert session.statements == []

    session.execute = lambda stmt: session.statements.append(stmt) or SimpleNamespace(rowcount=2)
    assert repo.delete_many(["A1", "B2"]) == 2
    assert "DELETE FROM hs_cases WHERE hs_cases.doc_id IN" in session.last_sql()


def test_문서_ID_전체_조회는_문서_ID_칸만_읽는다(session):
    assert HsCaseRepository(session).list_doc_ids() == set()
    assert " ".join(session.last_sql().split()) == "SELECT hs_cases.doc_id FROM hs_cases"
