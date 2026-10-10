"""CLIP 결정사례 모델의 제약을 DB 없이 검증한다."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.models import HsCase


def test_결정사례는_문서_ID로_중복_적재되지_않는다():
    assert HsCase.__table__.c.doc_id.unique is True


def test_HS_코드는_숫자_10자리_길이로_저장한다():
    # 세관장확인 조회는 숫자 10자리만 받음 (#182)
    assert HsCase.__table__.c.hs_code.type.length == 10


def test_결정사례_임베딩은_HNSW_코사인_인덱스로_검색한다():
    # IVFFlat은 데이터가 적으면 결과 누락 (#247)
    (index,) = [index for index in HsCase.__table__.indexes if index.name == "ix_hs_cases_embedding"]

    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
