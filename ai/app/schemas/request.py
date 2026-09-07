"""진단 엔드포인트 요청 스키마."""

from pydantic import Field

from .base import StrictModel


class TextDiagnoseRequest(StrictModel):
    """텍스트 기반 진단 요청.

    Args:
        product_id: 상품 식별자.
        text_blocks: 상품 상세페이지에서 복사한 텍스트 블록 목록.
        source_url: 출처 표시용 URL (선택).
    """

    product_id: str = Field(min_length=1)
    text_blocks: list[str] = Field(min_length=1)
    source_url: str | None = None


class ImageDiagnoseRequest(StrictModel):
    """이미지 기반 진단 요청.

    Args:
        product_id: 상품 식별자.
        image_urls: base64 data URI 또는 이미지 URL 목록.
        text_blocks: 보조 텍스트 (선택).
        source_url: 출처 표시용 URL (선택).
    """

    product_id: str = Field(min_length=1)
    image_urls: list[str] = Field(min_length=1)
    text_blocks: list[str] = Field(default_factory=list)
    source_url: str | None = None


class UrlDiagnoseRequest(StrictModel):
    """URL 기반 진단 요청. 서버가 직접 크롤링한다 (추후 구현).

    Args:
        product_id: 상품 식별자.
        source_url: 크롤링할 상품 페이지 URL.
    """

    product_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
