from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cosmetic import CosmeticIngredient
from app.repositories.base import BaseRepository


class CosmeticIngredientRepository(BaseRepository[CosmeticIngredient]):
    """화장품 규제성분 Repository."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CosmeticIngredient)

    def search_by_name(self, name: str) -> list[CosmeticIngredient]:
        """성분명(한글)으로 부분 검색한다.

        Args:
            name: 검색할 성분명 (부분 일치).

        Returns:
            list[CosmeticIngredient]: 매칭된 규제성분 리스트.
        """
        stmt = select(CosmeticIngredient).where(
            CosmeticIngredient.ingredient_name_ko.contains(name),
        )
        return list(self.session.scalars(stmt).all())
