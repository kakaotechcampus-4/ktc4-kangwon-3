from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.law import LawArticle
from app.repositories.base import BaseRepository


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
