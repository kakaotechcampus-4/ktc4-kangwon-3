from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.law import Law, LawArticle
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


class LawArticleRepository(BaseRepository[LawArticle]):
    """법령 조문 Repository. 벡터 유사도 검색을 지원한다."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, LawArticle)

    def search_by_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[LawArticle, float]]:
        """코사인 유사도 기반 벡터 검색.

        Args:
            query_vector: 1536차원 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.

        Returns:
            list[tuple[LawArticle, float]]: (조문, 코사인 거리) 쌍.
                거리가 작을수록 유사하다.
        """
        distance = LawArticle.embedding.cosine_distance(query_vector)
        stmt = (
            select(LawArticle, distance.label("distance"))
            .where(LawArticle.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )
        return [(row.LawArticle, row.distance) for row in self.session.execute(stmt)]

    def get_by_law_id(self, law_id: int) -> list[LawArticle]:
        """특정 법령의 조문 전체를 조회한다.

        Args:
            law_id: 법령 PK.

        Returns:
            list[LawArticle]: 해당 법령의 조문 리스트.
        """
        stmt = (
            select(LawArticle)
            .where(LawArticle.law_id == law_id)
            .order_by(LawArticle.article_no, LawArticle.article_branch)
        )
        return list(self.session.scalars(stmt).all())
