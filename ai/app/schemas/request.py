"""진단 엔드포인트 요청 스키마."""

from pydantic import Field, model_validator

from .base import ApiModel, StrictModel


class ContentDiagnoseRequest(StrictModel):
    """텍스트·이미지 통합 진단 요청. 둘 중 하나 이상 필수.

    Args:
        product_id: 상품 식별자.
        text_blocks: 상품 상세페이지에서 복사한 텍스트 블록 목록.
        images_base64: base64 data URI 또는 이미지 URL 목록.
        source_url: 출처 표시용 URL (선택).
    """

    product_id: str = Field(min_length=1)
    text_blocks: list[str] = Field(default_factory=list)
    images_base64: list[str] = Field(default_factory=list)
    source_url: str | None = None

    @model_validator(mode="after")
    def at_least_one_input(self):
        if not self.text_blocks and not self.images_base64:
            raise ValueError("text_blocks 또는 images_base64 중 하나는 필수입니다.")
        return self


class UrlDiagnoseRequest(StrictModel):
    """URL 기반 진단 요청. 서버가 직접 크롤링한다.

    Args:
        product_id: 상품 식별자.
        source_url: 크롤링할 상품 페이지 URL.
    """

    product_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)


class DiagnosisProductInput(ApiModel):
    """진단서에 담긴 상품 하나. 텍스트·이미지 중 하나 이상 필수.

    Args:
        product_id: BE 상품 ID (UUID v7). 세션 ID로 사용.
        text_blocks: 상품 상세페이지에서 복사한 텍스트 블록 목록.
        images_base64: base64 data URI 또는 이미지 URL 목록.
        source_url: 출처 표시용 URL (선택).
    """

    product_id: str = Field(min_length=1)
    text_blocks: list[str] = Field(default_factory=list)
    images_base64: list[str] = Field(default_factory=list)
    source_url: str | None = None

    @model_validator(mode="after")
    def at_least_one_input(self):
        if not self.text_blocks and not self.images_base64:
            raise ValueError("textBlocks 또는 imagesBase64 중 하나는 필수입니다.")
        return self


class DiagnosisRequest(ApiModel):
    """진단서 한 건의 상품들을 한 번에 접수하는 요청 (#263).

    Args:
        diagnosis_id: BE 진단서 ID.
        products: 진단할 상품 목록. 1~10개, productId 중복 불가.
    """

    diagnosis_id: str = Field(min_length=1)
    # 이미지 base64가 본문에 들어가 요청 크기 제한용 상한
    products: list[DiagnosisProductInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_product_ids(self):
        ids = [product.product_id for product in self.products]
        duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
        if duplicates:
            raise ValueError(f"productId가 중복됩니다: {', '.join(duplicates)}")
        return self
