from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base

# text-embedding-3-small 출력 차원 (utils/embedding.py)
EMBEDDING_DIM = 1536


class HsCase(Base):
    """관세청 CLIP 품목분류 결정사례와 임베딩. 통관 Tool이 비슷한 사례를 찾는 데 쓴다.

    칸은 CLIP 응답(CLIPCase)과 같다. 꺼낼 때 통관 Tool의 HsCase로 그대로 옮길 수 있다.
    """

    __tablename__ = "hs_cases"
    __table_args__ = (
        # 데이터 양과 관계없이 검색 품질 유지, 빈 테이블에서도 생성 가능 (#247)
        # halfvec: 1536차원 float4 대비 용량 절반, 검색 품질 차이 무시할 수준
        Index(
            "ix_hs_cases_embedding", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
    )

    doc_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # 구성품별 분리 분류면 여러 개(최대 4개 실측), 6단위까지만 결정된 사례는 6자리
    hs_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False)
    # 물품명 최대 596자 실측 (2026-10-19 스냅샷 13,679건)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    # YYYYMMDD (CLIP ENFR_DT 그대로)
    enforce_date: Mapped[str | None] = mapped_column(String(8))
    embedding = mapped_column(HALFVEC(EMBEDDING_DIM))
    # 검색 전 모델 일치 확인용 (모델이 다르면 벡터 공간이 다름)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
