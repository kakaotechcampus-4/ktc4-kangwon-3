"""법령·조문 모델의 제약을 DB 없이 검증한다."""

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.models import Law, LawArticle


def _unique_column_sets(table) -> list[set[str]]:
    sets = [
        {column.name for column in constraint.columns}
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    return sets + [{column.name} for column in table.columns if column.unique]


def test_법령은_법령일련번호로_고유하다():
    # 법령ID(law_code)와 법령일련번호(MST)는 다른 값. 본문 조회 기준은 MST (#183)
    assert {"law_mst"} in _unique_column_sets(Law.__table__)
    assert {"law_code"} not in _unique_column_sets(Law.__table__)


def test_조문은_법령_조문번호_가지번호_조합으로_고유하다():
    assert {"law_id", "article_no", "article_branch"} in _unique_column_sets(LawArticle.__table__)


def test_법령을_지우면_조문도_DB에서_함께_지운다():
    # 잘못 적재한 법령 정리용. 개정 시에는 is_current=False로 비활성화 (#161)
    (foreign_key,) = LawArticle.__table__.c.law_id.foreign_keys

    assert foreign_key.column is Law.__table__.c.law_id
    assert foreign_key.ondelete == "CASCADE"


def test_조문_임베딩은_HNSW_코사인_인덱스로_검색한다():
    # IVFFlat은 데이터가 적으면 결과 누락 (#247)
    (index,) = [index for index in LawArticle.__table__.indexes if index.name == "ix_law_articles_embedding"]

    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
