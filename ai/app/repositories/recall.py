from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
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

    def get_by_source_uid(self, source: str, source_uid: str) -> Recall | None:
        """출처와 원본 리콜 ID로 조회한다.

        Args:
            source: 출처 구분 ('domestic' 또는 'foreign').
            source_uid: 원본 리콜 ID.

        Returns:
            Recall | None: 리콜사례. 없으면 None.
        """
        stmt = select(Recall).where(Recall.source == source, Recall.source_uid == source_uid)
        return self.session.scalars(stmt).first()

    def upsert_many(self, rows: list[dict[str, Any]], *, batch_size: int = 1000) -> int:
        """(source, source_uid) 기준으로 리콜사례를 저장하거나 갱신한다.

        이미 있는 리콜은 rows에 담긴 컬럼만 갱신하고 fetched_at을 현재 시각으로 바꾼다.
        rows에 embedding이 없으면 기존 임베딩은 유지된다.
        같은 (source, source_uid)가 rows에 여러 번 있으면 마지막 값만 저장한다.

        Args:
            rows: Recall 컬럼명을 키로 하는 dict 리스트. 모든 dict는 같은 키를 가져야 하며
                source, source_uid는 필수.
            batch_size: 한 번의 INSERT에 담을 행 수.

        Returns:
            int: 저장 또는 갱신된 행 수.
        """
        unique_rows = list({(row["source"], row["source_uid"]): row for row in rows}.values())
        if not unique_rows:
            return 0

        affected = 0
        for start in range(0, len(unique_rows), batch_size):
            stmt = insert(Recall).values(unique_rows[start:start + batch_size])
            update_columns = {
                key: stmt.excluded[key]
                for key in unique_rows[0]
                if key not in ("recall_id", "source", "source_uid")
            }
            update_columns["fetched_at"] = func.now()
            stmt = stmt.on_conflict_do_update(
                index_elements=["source", "source_uid"], set_=update_columns,
            ).returning(Recall.recall_id)
            affected += len(self.session.execute(stmt).all())     # rowcount는 psycopg에서 -1 반환
        self.session.flush()
        return affected
