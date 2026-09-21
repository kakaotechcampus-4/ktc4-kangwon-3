from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HsCase(Base):
    """관세청 CLIP 품목분류 결정사례. 인식 에이전트가 HS코드 분류에 사용한다."""

    __tablename__ = "hs_cases"
    __table_args__ = (
        Index("ix_hs_cases_hs_code", "hs_code"),
        Index(
            "ix_hs_cases_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 50},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    hs_case_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    hs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    enforce_date: Mapped[date | None] = mapped_column(Date)
    embedding = mapped_column(Vector(1536))
