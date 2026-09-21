from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Recall(Base):
    """국표원 리콜사례 (국내+해외 통합). 판정 에이전트가 유사 리콜 매칭에 사용한다."""

    __tablename__ = "recalls"
    __table_args__ = (
        Index("ix_recalls_source", "source"),
        Index("ix_recalls_product_name", "product_name"),
        Index(
            "ix_recalls_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 50},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    recall_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    source_uid: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(500))
    brand_name: Mapped[str | None] = mapped_column(String(200))
    model_name: Mapped[str | None] = mapped_column(String(500))
    maker_name: Mapped[str | None] = mapped_column(String(200))
    making_country: Mapped[str | None] = mapped_column(String(100))
    recall_type: Mapped[str | None] = mapped_column(String(100))
    recall_means: Mapped[str | None] = mapped_column(String(200))
    harm_description: Mapped[str | None] = mapped_column(Text)
    accident_description: Mapped[str | None] = mapped_column(Text)
    action_description: Mapped[str | None] = mapped_column(Text)
    publish_date: Mapped[str | None] = mapped_column(String(20))
    embedding = mapped_column(Vector(1536))
