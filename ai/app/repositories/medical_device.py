from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.medical_device import MedicalDevice
from app.repositories.base import BaseRepository


class MedicalDeviceRepository(BaseRepository[MedicalDevice]):
    """의료기기 품목 Repository."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, MedicalDevice)

    def get_by_classification(self, classification_no: str) -> list[MedicalDevice]:
        """품목분류번호로 조회한다.

        Args:
            classification_no: 품목분류번호.

        Returns:
            list[MedicalDevice]: 해당 분류의 의료기기 리스트.
        """
        stmt = select(MedicalDevice).where(
            MedicalDevice.classification_no == classification_no,
        )
        return list(self.session.scalars(stmt).all())

    def search_by_name(self, name: str) -> list[MedicalDevice]:
        """품목명으로 부분 검색한다.

        Args:
            name: 검색할 품목명 (부분 일치).

        Returns:
            list[MedicalDevice]: 매칭된 의료기기 리스트.
        """
        stmt = select(MedicalDevice).where(
            MedicalDevice.product_name.contains(name),
        )
        return list(self.session.scalars(stmt).all())
