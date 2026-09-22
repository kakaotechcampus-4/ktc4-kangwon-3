"""관세청 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel, Field


class CLIPSearchRequest(BaseModel):
    """CLIP 품목분류 결정사례 검색 요청.

    Args:
        query: 검색어 (예: "드론", "블루투스 이어폰").
        page: 페이지 번호. 기본 1.
        page_size: 페이지당 건수. 기본 50.
    """

    query: str = Field(min_length=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class CustomsGwConfirmationRequest(BaseModel):
    """세관장확인대상물품 조회 요청.

    Args:
        hs_code: HS 품목코드. 10자리 풀코드를 넣어야 결과가 나온다.
        import_export: 수출입 구분. "1"=수출, "2"=수입. 기본값 수입.
    """

    hs_code: str = Field(min_length=1)
    import_export: str = Field(default="2", pattern=r"^[12]$")
