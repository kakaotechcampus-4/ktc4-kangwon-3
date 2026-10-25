from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class ApiResponseCache(Base):
    """외부 API 응답 캐시. 클라이언트 이름과 요청 해시로 한 건을 찾는다.

    클라이언트가 해석까지 끝낸 응답 스키마를 JSON으로 저장한다. 꺼낼 때 같은 스키마로 되돌리면
    클라이언트를 직접 부른 결과와 같다.
    """

    __tablename__ = "api_response_cache"
    __table_args__ = (
        # 만료 행 정리용
        Index("ix_api_response_cache_expires_at", "expires_at"),
    )

    client: Mapped[str] = mapped_column(String(50), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # None이면 영구 보관 (버전이 고정된 본문)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
