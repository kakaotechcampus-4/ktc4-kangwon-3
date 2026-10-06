from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Law(Base):
    """법제처 법령 메타정보."""

    __tablename__ = "laws"
    __table_args__ = (
        Index("ix_laws_name_ko", "name_ko"),
        Index("ix_laws_law_type", "law_type"),
    )

    law_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    law_mst: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    law_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ko: Mapped[str] = mapped_column(String(200), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(100))
    law_type: Mapped[str] = mapped_column(String(30), nullable=False)
    enforcement_date: Mapped[date | None] = mapped_column(Date)
    competent_authority: Mapped[str | None] = mapped_column(String(100))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)

    articles: Mapped[list["LawArticle"]] = relationship(
        back_populates="law", cascade="all, delete-orphan", passive_deletes=True,
    )


class LawArticle(Base):
    """법제처 법령 조문 텍스트 + 임베딩. RAG 검색 대상."""

    __tablename__ = "law_articles"
    __table_args__ = (
        UniqueConstraint("law_id", "article_no", "article_branch"),
        Index("ix_law_articles_law_id", "law_id"),
    )

    law_article_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    law_id: Mapped[int] = mapped_column(
        ForeignKey("laws.law_id", ondelete="CASCADE"), nullable=False,
    )
    article_no: Mapped[int] = mapped_column(Integer, nullable=False)
    article_branch: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(300))
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    enforcement_date: Mapped[date | None] = mapped_column(Date)
    embedding = mapped_column(Vector(1536))

    law: Mapped["Law"] = relationship(back_populates="articles")
