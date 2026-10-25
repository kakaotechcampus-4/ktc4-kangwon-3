from sqlalchemy import exists, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.hs_case import EMBEDDING_DIM, HsCase
from app.db.repositories.base import BaseRepository


class HsCaseRepository(BaseRepository[HsCase]):
    """CLIP 결정사례 Repository. 벡터 유사도 검색을 지원한다. 트랜잭션(commit)은 호출부 책임."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, HsCase)

    def search_by_vector(
        self,
        query_vector: list[float],
        *,
        embedding_model: str,
        top_k: int = 5,
    ) -> list[tuple[HsCase, float]]:
        """코사인 유사도 기반 벡터 검색. 같은 임베딩 모델로 만든 행만 본다.

        Args:
            query_vector: 1536차원 쿼리 임베딩 벡터.
            embedding_model: 쿼리 벡터를 만든 임베딩 모델 이름.
            top_k: 반환할 최대 결과 수.

        Returns:
            list[tuple[HsCase, float]]: (결정사례, 코사인 거리) 쌍.
                거리가 작을수록 유사하다.

        Raises:
            ValueError: 쿼리 벡터 차원이 1536이 아닌 경우.
        """
        if len(query_vector) != EMBEDDING_DIM:
            raise ValueError(f"쿼리 벡터는 {EMBEDDING_DIM}차원이어야 합니다 (받은 값 {len(query_vector)}차원).")
        distance = HsCase.embedding.cosine_distance(query_vector)
        stmt = (
            select(HsCase, distance.label("distance"))
            .where(HsCase.embedding.is_not(None), HsCase.embedding_model == embedding_model)
            .order_by(distance)
            .limit(top_k)
        )
        return [(row.HsCase, row.distance) for row in self.session.execute(stmt)]

    def get_by_hs_code(self, hs_code: str) -> list[HsCase]:
        """HS코드로 결정사례를 조회한다. 자릿수가 달라도 앞자리가 겹치면 같은 계열로 본다.

        "841459"(6자리)로 찾으면 8414.59로 시작하는 10자리 사례를, "8414599000"(10자리)로 찾으면
        같은 10자리 사례와 6단위까지만 결정된 "841459" 사례를 함께 돌려준다.

        Args:
            hs_code: 조회할 HS코드(숫자만).

        Returns:
            list[HsCase]: 해당 HS코드의 결정사례 리스트.
        """
        code = func.unnest(HsCase.hs_codes).column_valued("code")
        query = literal(hs_code)
        matches = exists(select(1).where(code.startswith(query) | query.startswith(code)))
        stmt = select(HsCase).where(matches)
        return list(self.session.scalars(stmt).all())

    def get_many(self, doc_ids: list[str]) -> list[HsCase]:
        """문서 ID 여러 개로 결정사례를 조회한다. 없는 ID는 건너뛴다.

        Args:
            doc_ids: 조회할 문서 ID 목록.

        Returns:
            list[HsCase]: 찾은 결정사례(순서는 보장하지 않음).
        """
        if not doc_ids:
            return []
        stmt = select(HsCase).where(HsCase.doc_id.in_(doc_ids))
        return list(self.session.scalars(stmt).all())

    def upsert_many(self, cases: list[HsCase]) -> None:
        """결정사례를 일괄 저장한다. 같은 문서 ID가 있으면 내용·임베딩·수집 시각을 덮어쓴다.

        Args:
            cases: 저장할 결정사례.
        """
        if not cases:
            return
        columns = ("doc_id", "hs_codes", "product_name", "description", "decision_reason", "enforce_date",
                   "embedding", "embedding_model")
        stmt = insert(HsCase).values([{name: getattr(case, name) for name in columns} for case in cases])
        stmt = stmt.on_conflict_do_update(
            index_elements=[HsCase.doc_id],
            set_={**{name: stmt.excluded[name] for name in columns if name != "doc_id"}, "fetched_at": func.now()},
        )
        self.session.execute(stmt)
