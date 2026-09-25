from datetime import date

from sqlalchemy import Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomsConfirmation(Base):
    """관세청 세관장확인대상물품. HS코드별 필요 법령·기관·서류."""

    __tablename__ = "customs_confirmations"
    __table_args__ = (
        Index("ix_customs_confirmations_hs_code", "hs_code"),
    )

    customs_confirmation_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True,
    )
    hs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    import_export: Mapped[str] = mapped_column(String(1), nullable=False)
    law_name: Mapped[str | None] = mapped_column(String(200))
    agency_name: Mapped[str | None] = mapped_column(String(100))
    document_name: Mapped[str | None] = mapped_column(String(300))
    apply_start_date: Mapped[date | None] = mapped_column(Date)
