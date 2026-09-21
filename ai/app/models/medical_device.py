from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MedicalDevice(Base):
    """식약처 의료기기 품목정보."""

    __tablename__ = "medical_devices"
    __table_args__ = (
        Index("ix_medical_devices_classification_no", "classification_no"),
        Index("ix_medical_devices_product_name", "product_name"),
    )

    medical_device_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True,
    )
    device_sn: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    classification_no: Mapped[str | None] = mapped_column(String(30))
    grade: Mapped[str | None] = mapped_column(String(5))
    permission_type: Mapped[str | None] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(30))
    purpose: Mapped[str | None] = mapped_column(Text)
