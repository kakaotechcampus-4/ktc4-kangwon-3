from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class DiagnosisSessionRecord(Base):
    """재시작 때 되살릴 진단 세션. 상품 하나에 한 행.

    세션 전체를 JSON으로 담아 그대로 되돌린다. 나머지 칸은 복원·정리 때 고르는 용도.
    fetched_at은 마지막으로 쓴 시각.
    """

    __tablename__ = "diagnosis_sessions"

    product_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 세션의 마지막 변경 시각 (답변 대기 보관 시간 기준)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session: Mapped[dict] = mapped_column(JSONB, nullable=False)
