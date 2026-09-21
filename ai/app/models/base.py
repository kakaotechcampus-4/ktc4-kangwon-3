from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속할 베이스 클래스.

    Attributes:
        fetched_at: 데이터 수집 일시. INSERT 시 자동으로 현재 시각이 들어간다.
    """

    __abstract__ = True

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
