"""관세청 외부 API 응답 모델."""

from pydantic import BaseModel


class CLIPCase(BaseModel):
    """CLIP 품목분류 결정사례 단건."""

    hs_code: str
    product_name: str
    description: str
    decision_reason: str
    doc_id: str | None = None
    enforce_date: str | None = None


class CLIPSearchResponse(BaseModel):
    """CLIP 품목분류 결정사례 검색 응답.

    Attributes:
        total_count: 전체 검색 건수.
        items: 결정사례 목록.
    """

    total_count: int
    items: list[CLIPCase]


class CustomsGwConfirmation(BaseModel):
    """세관장확인대상물품 단건."""

    hs_code: str | None = None
    law_code: str | None = None
    law_name: str | None = None
    req_agency_code: str | None = None
    req_agency_name: str | None = None
    confirm_agency_name: str | None = None
    apply_start_date: str | None = None


class CustomsGwConfirmationResponse(BaseModel):
    """세관장확인대상물품 조회 응답.

    Attributes:
        items: 확인대상물품 목록.
    """

    items: list[CustomsGwConfirmation]
