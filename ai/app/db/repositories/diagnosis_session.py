from collections.abc import Collection

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.diagnosis_session import DiagnosisSessionRecord


class DiagnosisSessionRepository:
    """진단 세션 보관 Repository. 트랜잭션(commit)은 호출부 책임.

    PK가 문자열(상품 ID)이라 BaseRepository를 상속하지 않는다.

    Attributes:
        session: SQLAlchemy DB 세션.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def put(self, record: DiagnosisSessionRecord) -> None:
        """세션 한 건을 저장한다. 같은 상품이 있으면 덮어쓴다.

        Args:
            record: 저장할 세션 행.
        """
        values = {
            "product_id": record.product_id,
            "status": record.status,
            "run_type": record.run_type,
            "updated_at": record.updated_at,
            "session": record.session,
        }
        stmt = insert(DiagnosisSessionRecord).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[DiagnosisSessionRecord.product_id],
            set_={
                **{key: stmt.excluded[key] for key in values if key != "product_id"},
                "fetched_at": func.now(),
            },
        )
        self.session.execute(stmt)

    def delete(self, product_ids: Collection[str]) -> int:
        """세션들을 지운다. 없는 상품은 건너뛴다.

        Args:
            product_ids: 지울 상품 ID.

        Returns:
            int: 지운 행 수.
        """
        if not product_ids:
            return 0
        stmt = delete(DiagnosisSessionRecord).where(DiagnosisSessionRecord.product_id.in_(product_ids))
        return self.session.execute(stmt).rowcount

    def load_all(self) -> list[DiagnosisSessionRecord]:
        """보관된 세션을 모두 읽는다. 재시작 때 복원용.

        Returns:
            list[DiagnosisSessionRecord]: 세션 행. 오래 바뀌지 않은 순.
        """
        stmt = select(DiagnosisSessionRecord).order_by(DiagnosisSessionRecord.updated_at)
        return list(self.session.scalars(stmt).all())
