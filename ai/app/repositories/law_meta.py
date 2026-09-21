from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.law import Law
from app.repositories.base import BaseRepository


class LawRepository(BaseRepository[Law]):
    """법령 메타정보 Repository."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Law)

    def get_by_mst(self, law_mst: str) -> Law | None:
        """법령일련번호로 조회한다.

        Args:
            law_mst: 법령일련번호.

        Returns:
            Law | None: 법령. 없으면 None.
        """
        stmt = select(Law).where(Law.law_mst == law_mst)
        return self.session.scalars(stmt).first()

    def search_by_name(self, name: str) -> list[Law]:
        """법령명으로 부분 검색한다.

        Args:
            name: 검색할 법령명 (부분 일치).

        Returns:
            list[Law]: 매칭된 법령 리스트.
        """
        stmt = select(Law).where(Law.name_ko.contains(name))
        return list(self.session.scalars(stmt).all())

    def get_current_laws(self) -> list[Law]:
        """현행 법령만 조회한다.

        Returns:
            list[Law]: 현행 법령 리스트.
        """
        stmt = select(Law).where(Law.is_current.is_(True))
        return list(self.session.scalars(stmt).all())
