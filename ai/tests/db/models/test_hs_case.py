"""CLIP 결정사례 모델의 제약을 DB 없이 검증한다."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.db.models import HsCase
from app.schemas.clients.customs_response import CLIPCase


def test_결정사례는_문서_ID가_키라_다시_적재해도_같은_행이다():
    assert [column.name for column in HsCase.__table__.primary_key] == ["doc_id"]


def test_HS_코드는_여러_개를_숫자_10자리_이하로_저장한다():
    # 구성품별 분리 분류는 코드가 여러 개, 세관장확인 조회는 숫자 10자리만 받음 (#182)
    column = HsCase.__table__.c.hs_codes

    assert isinstance(column.type, postgresql.ARRAY)
    assert column.type.item_type.length == 10
    assert column.nullable is False


def test_칸은_CLIP_응답과_같다():
    clip_fields = set(CLIPCase.model_fields)

    assert clip_fields <= {column.name for column in HsCase.__table__.columns}
    assert HsCase.__table__.c.product_name.type.length is None  # 물품명 596자 실측, 길이 제한 없음


def test_결정사례_임베딩은_halfvec_HNSW_코사인_인덱스로_검색한다():
    # IVFFlat은 데이터가 적으면 결과 누락 (#247)
    (index,) = [index for index in HsCase.__table__.indexes if index.name == "ix_hs_cases_embedding"]

    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "USING hnsw (embedding halfvec_cosine_ops)" in sql
