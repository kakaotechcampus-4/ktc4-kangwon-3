from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """모든 Repository가 상속할 공통 CRUD 베이스.

    Attributes:
        session: SQLAlchemy DB 세션.
        model: ORM 모델 클래스.
    """

    def __init__(self, session: Session, model: type[T]) -> None:
        self.session = session
        self.model = model

    def get_by_id(self, entity_id: int) -> T | None:
        """PK로 단일 엔티티를 조회한다.

        Args:
            entity_id: 조회할 엔티티의 PK.

        Returns:
            T | None: 엔티티. 없으면 None.
        """
        return self.session.get(self.model, entity_id)

    def get_all(self, *, offset: int = 0, limit: int = 100) -> list[T]:
        """엔티티 목록을 페이징 조회한다.

        Args:
            offset: 건너뛸 행 수.
            limit: 최대 반환 행 수.

        Returns:
            list[T]: 엔티티 리스트.
        """
        stmt = select(self.model).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def create(self, entity: T) -> T:
        """엔티티를 저장한다.

        Args:
            entity: 저장할 ORM 인스턴스.

        Returns:
            T: PK가 채워진 엔티티.
        """
        self.session.add(entity)
        self.session.flush()
        return entity

    def create_many(self, entities: list[T]) -> list[T]:
        """여러 엔티티를 일괄 저장한다.

        Args:
            entities: 저장할 ORM 인스턴스 리스트.

        Returns:
            list[T]: PK가 채워진 엔티티 리스트.
        """
        self.session.add_all(entities)
        self.session.flush()
        return entities

    def update(self, entity_id: int, **kwargs: Any) -> T | None:
        """PK로 엔티티를 찾아 필드를 수정한다.

        Args:
            entity_id: 수정할 엔티티의 PK.
            **kwargs: 수정할 필드명과 값.

        Returns:
            T | None: 수정된 엔티티. 없으면 None.
        """
        entity = self.get_by_id(entity_id)
        if entity is None:
            return None
        for key, value in kwargs.items():
            setattr(entity, key, value)
        self.session.flush()
        return entity

    def delete(self, entity_id: int) -> bool:
        """PK로 엔티티를 삭제한다.

        Args:
            entity_id: 삭제할 엔티티의 PK.

        Returns:
            bool: 삭제 성공 여부.
        """
        entity = self.get_by_id(entity_id)
        if entity is None:
            return False
        self.session.delete(entity)
        self.session.flush()
        return True
