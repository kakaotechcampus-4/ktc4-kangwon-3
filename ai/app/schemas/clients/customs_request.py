"""관세청 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel, Field


class CLIPSearchRequest(BaseModel):
    """CLIP 품목분류 결정사례 검색 요청.

    Args:
        query: 검색어 (예: "드론", "블루투스 이어폰").
        page: 페이지 번호. 기본 1.
        page_size: 페이지당 건수. 기본 10, 최대 100 (1000건 요청 시 0건 응답).
    """

    query: str = Field(min_length=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class CustomsGwConfirmationRequest(BaseModel):
    """세관장확인대상물품 조회 요청.

    Args:
        hs_code: HS 품목코드. 숫자 10자리만 허용한다.
            점이 남은 값이나 4자리 HS는 API가 오류 없이 0건을 돌려줘서 "요건 없음"과 구분할 수 없다.
        import_export: 수출입 구분. "1"=수출, "2"=수입. 기본값 수입.
    """

    hs_code: str = Field(pattern=r"^\d{10}$")
    import_export: str = Field(default="2", pattern=r"^[12]$")
