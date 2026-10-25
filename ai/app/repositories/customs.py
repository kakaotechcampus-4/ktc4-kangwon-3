from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hs_case import HsCase
from app.repositories.base import BaseRepository


class HsCaseRepository(BaseRepository[HsCase]):
    """CLIP 결정사례 Repository. 벡터 유사도 검색을 지원한다."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, HsCase)

    def search_by_vector(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[tuple[HsCase, float]]:
        """코사인 유사도 기반 벡터 검색.

        Args:
            query_vector: 1536차원 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.

        Returns:
            list[tuple[HsCase, float]]: (결정사례, 코사인 거리) 쌍.
                거리가 작을수록 유사하다.
        """
        distance = HsCase.embedding.cosine_distance(query_vector)
        stmt = (
            select(HsCase, distance.label("distance"))
            .where(HsCase.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )
        return [(row.HsCase, row.distance) for row in self.session.execute(stmt)]

    def get_by_hs_code(self, hs_code: str) -> list[HsCase]:
        """HS코드로 결정사례를 조회한다.

        Args:
            hs_code: 조회할 HS코드.

        Returns:
            list[HsCase]: 해당 HS코드의 결정사례 리스트.
        """
        stmt = select(HsCase).where(HsCase.hs_code == hs_code)
        return list(self.session.scalars(stmt).all())
