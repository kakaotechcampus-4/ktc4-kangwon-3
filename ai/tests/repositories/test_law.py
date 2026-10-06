"""법령·조문 Repository가 만드는 SQL을 DB 없이 검증한다."""

from app.repositories.law import LawArticleRepository, LawRepository


def test_법령일련번호로_조회한다(session):
    LawRepository(session).get_by_mst("273575")

    assert "WHERE laws.law_mst = %(law_mst_1)s" in session.last_sql()


def test_법령명은_부분_일치로_검색한다(session):
    LawRepository(session).search_by_name("전기용품")

    assert "laws.name_ko LIKE '%%' || %(name_ko_1)s || '%%'" in session.last_sql()


def test_현행_법령만_조회한다(session):
    LawRepository(session).get_current_laws()

    assert "WHERE laws.is_current IS true" in session.last_sql()


def test_조문_벡터_검색은_임베딩_없는_행을_빼고_코사인_거리순으로_top_k만_가져온다(session):
    LawArticleRepository(session).search_by_vector([0.1] * 1536, top_k=3)

    sql = session.last_sql()
    assert "law_articles.embedding <=> %(embedding_1)s AS distance" in sql
    assert "WHERE law_articles.embedding IS NOT NULL" in sql
    assert "ORDER BY law_articles.embedding <=> %(embedding_1)s" in sql
    assert session.statements[-1].compile().params["param_1"] == 3


def test_법령의_조문은_조문번호_가지번호_순서로_조회한다(session):
    LawArticleRepository(session).get_by_law_id(1)

    sql = session.last_sql()
    assert "WHERE law_articles.law_id = %(law_id_1)s" in sql
    assert "ORDER BY law_articles.article_no, law_articles.article_branch" in sql
