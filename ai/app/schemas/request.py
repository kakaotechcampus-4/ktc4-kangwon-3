"""진단 엔드포인트 요청 스키마."""

from pydantic import Field, model_validator

from .base import StrictModel


class ContentDiagnoseRequest(StrictModel):
    """텍스트·이미지 통합 진단 요청. 둘 중 하나 이상 필수."""

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
    """URL 기반 진단 요청. 서버가 직접 크롤링한다."""

    product_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
