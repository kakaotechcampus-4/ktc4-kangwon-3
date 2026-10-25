"""판매 사이트 상품 페이지 요청 모델."""

from pydantic import BaseModel, Field


class ProductPageRequest(BaseModel):
    """상품 페이지 조회 요청.

    Args:
        url: 상품 페이지 전체 주소. 판매자마다 하위 도메인이 달라 주소 전체로 요청.
    """

    url: str = Field(pattern=r"^https?://\S+$")
