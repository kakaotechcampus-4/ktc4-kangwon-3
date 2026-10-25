from datetime import datetime

from sqlalchemy import DateTime, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApiResponseCache(Base):
    """외부 API 응답 원문 캐시. 클라이언트 이름과 요청 해시로 한 건을 찾는다.

    원문만 저장해 파서가 바뀌어도 다시 조회하지 않고 해석만 다시 한다.
    """

    __tablename__ = "api_response_cache"
    __table_args__ = (
        # 만료 행 정리용
        Index("ix_api_response_cache_expires_at", "expires_at"),
    )

    client: Mapped[str] = mapped_column(String(50), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # None이면 영구 보관 (버전이 고정된 본문)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
