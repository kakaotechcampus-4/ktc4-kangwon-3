from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recall import Recall
from app.repositories.base import BaseRepository


class RecallRepository(BaseRepository[Recall]):
    """리콜사례 Repository. 벡터 유사도 검색을 지원한다."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Recall)

    def search_by_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[Recall, float]]:
        """코사인 유사도 기반 벡터 검색.

        Args:
            query_vector: 1536차원 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.

        Returns:
            list[tuple[Recall, float]]: (리콜사례, 코사인 거리) 쌍.
                거리가 작을수록 유사하다.
        """
        distance = Recall.embedding.cosine_distance(query_vector)
        stmt = (
            select(Recall, distance.label("distance"))
            .where(Recall.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )
        return [(row.Recall, row.distance) for row in self.session.execute(stmt)]

    def get_by_source(self, source: str) -> list[Recall]:
        """출처별 리콜사례를 조회한다.

        Args:
            source: 출처 구분 ('domestic' 또는 'foreign').

        Returns:
            list[Recall]: 해당 출처의 리콜사례 리스트.
        """
        stmt = select(Recall).where(Recall.source == source)
        return list(self.session.scalars(stmt).all())
