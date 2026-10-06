from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CosmeticIngredient(Base):
    """식약처 화장품 규제성분 (배합금지/한도)."""

    __tablename__ = "cosmetic_ingredients"
    __table_args__ = (
        Index("ix_cosmetic_ingredients_name_ko", "ingredient_name_ko"),
    )

    cosmetic_ingredient_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True,
    )
    ingredient_name_ko: Mapped[str] = mapped_column(String(500), nullable=False)
    ingredient_name_en: Mapped[str | None] = mapped_column(String(500))
    prohibited_countries: Mapped[str | None] = mapped_column(String(200))
    limited_countries: Mapped[str | None] = mapped_column(String(200))
