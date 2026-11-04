"""진단 세션 보관 객체. 재시작 때 되살릴 세션을 diagnosis_sessions에 쓰고 읽는다.

DB를 못 쓰면 경고만 남기고 넘어가 진단은 메모리로 계속 돎. 실패 뒤 일정 시간은 DB를 건너뜀.
건너뛴 동안의 변경은 DB에 안 남아, 복원 때 이미 끝난 세션이 되살아날 수 있음
(다시 돌아도 BE가 이미 받은 결과·실패로 보고 무시함).
"""

import logging
from collections.abc import Callable, Collection

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..schemas.session import DiagnosisSession
from .fetchers import DbSkip
from .models.diagnosis_session import DiagnosisSessionRecord
from .repositories.diagnosis_session import DiagnosisSessionRepository

logger = logging.getLogger(__name__)

# DB 건너뛰기 로그 이름
_NAME = "진단 세션"


class SessionArchiveDatabase:
    """진단 세션을 DB에 보관하고 재시작 때 읽어 온다.

    Args:
        session_factory: DB 세션을 만드는 함수.
        skip: DB 건너뛰기 상태. None이면 이 객체 전용 (응답 캐시와 따로).
    """

    def __init__(self, session_factory: Callable[[], Session], *, skip: DbSkip | None = None):
        self._session_factory = session_factory
        self._skip = skip or DbSkip()

    def save(self, session: DiagnosisSession) -> None:
        """세션 한 건을 저장한다. 같은 상품이 있으면 덮어씀. DB를 못 쓰면 넘어감.

        Args:
            session: 저장할 세션.
        """
        if not self._skip.available():
            return
        record = DiagnosisSessionRecord(
            product_id=session.context.product_id, status=session.status.value,
            run_type=session.context.run_type.value, updated_at=session.updated_at,
            session=session.model_dump(mode="json"),
        )
        try:
            with self._session_factory() as db:
                DiagnosisSessionRepository(db).put(record)
                db.commit()
        except SQLAlchemyError as exc:
            self._skip.failed(_NAME, "저장", exc)

    def remove(self, product_ids: Collection[str]) -> None:
        """세션들을 지운다. DB를 못 쓰면 넘어감.

        Args:
            product_ids: 지울 상품 ID.
        """
        if not product_ids or not self._skip.available():
            return
        try:
            with self._session_factory() as db:
                DiagnosisSessionRepository(db).delete(product_ids)
                db.commit()
        except SQLAlchemyError as exc:
            self._skip.failed(_NAME, "삭제", exc)

    def load(self) -> list[DiagnosisSession]:
        """보관된 세션을 모두 읽는다. 지금 세션 모양과 안 맞는 행(배포로 바뀐 옛 행)은 경고 후 지움.

        Returns:
            list[DiagnosisSession]: 세션. 오래 바뀌지 않은 순. DB를 못 쓰면 빈 목록.
        """
        try:
            with self._session_factory() as db:
                repository = DiagnosisSessionRepository(db)
                sessions, broken = [], []
                for record in repository.load_all():
                    try:
                        sessions.append(DiagnosisSession.model_validate(record.session))
                    except ValidationError as exc:
                        broken.append(record.product_id)
                        logger.warning("보관된 진단 세션을 읽지 못해 지움 (product_id=%s): 오류 %d개",
                                       record.product_id, exc.error_count())
                if broken:
                    repository.delete(broken)
                    db.commit()
                return sessions
        except SQLAlchemyError as exc:
            self._skip.failed(_NAME, "읽기", exc)
            return []
