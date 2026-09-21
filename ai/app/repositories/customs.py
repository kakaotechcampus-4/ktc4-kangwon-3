from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customs import CustomsConfirmation
from app.repositories.base import BaseRepository


class CustomsConfirmationRepository(BaseRepository[CustomsConfirmation]):
    """세관장확인대상물품 Repository."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CustomsConfirmation)

    def get_by_hs_code(self, hs_code: str) -> list[CustomsConfirmation]:
        """HS코드로 확인대상물품을 조회한다.

        Args:
            hs_code: 조회할 HS코드.

        Returns:
            list[CustomsConfirmation]: 해당 HS코드의 확인대상물품 리스트.
        """
        stmt = select(CustomsConfirmation).where(
            CustomsConfirmation.hs_code == hs_code,
        )
        return list(self.session.scalars(stmt).all())
