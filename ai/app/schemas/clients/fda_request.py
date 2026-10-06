"""식약처 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel, Field


class FdaPaginationRequest(BaseModel):
    """식약처 API 공통 페이지네이션 요청.

    Args:
        page: 페이지 번호. 기본 1.
        num_of_rows: 페이지당 건수. 기본 10.
    """

    page: int = Field(default=1, ge=1)
    num_of_rows: int = Field(default=10, ge=1, le=100)


class MedicalDeviceRequest(FdaPaginationRequest):
    """의료기기 품목정보 조회 요청."""


class CosmeticsReglRequest(FdaPaginationRequest):
    """화장품 규제정보 조회 요청."""
