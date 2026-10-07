"""세관장확인·결정사례 Repository가 만드는 SQL을 DB 없이 검증한다."""

from app.repositories.customs import CustomsConfirmationRepository, HsCaseRepository


def test_세관장확인은_HS_코드로_조회한다(session):
    CustomsConfirmationRepository(session).get_by_hs_code("8414599000")

    assert "WHERE customs_confirmations.hs_code = %(hs_code_1)s" in session.last_sql()


def test_결정사례_벡터_검색은_임베딩_없는_행을_빼고_코사인_거리순으로_top_k만_가져온다(session):
    HsCaseRepository(session).search_by_vector([0.1] * 1536, top_k=5)

    sql = session.last_sql()
    assert "hs_cases.embedding <=> %(embedding_1)s AS distance" in sql
    assert "WHERE hs_cases.embedding IS NOT NULL" in sql
    assert "ORDER BY hs_cases.embedding <=> %(embedding_1)s" in sql
    assert session.statements[-1].compile().params["param_1"] == 5


def test_결정사례는_HS_코드로_조회한다(session):
    HsCaseRepository(session).get_by_hs_code("8414599000")

    assert "WHERE hs_cases.hs_code = %(hs_code_1)s" in session.last_sql()
