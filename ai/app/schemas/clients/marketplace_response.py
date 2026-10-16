"""판매 사이트 상품 페이지 응답 모델."""

from typing import Literal

from pydantic import BaseModel, Field


class ProductPageImage(BaseModel):
    """상품 페이지의 이미지 하나.

    Attributes:
        url: 원본 크기 이미지 주소. 추출에 넘기는 주소.
        thumbnail_url: 작은 크기 이미지 주소. 이미지 분류에 쓰는 주소 (작을수록 입력 토큰이 적음).
            사이트가 작은 크기를 주지 않으면 url과 같음.
        area: 페이지 안 위치. gallery=상품 사진 모음, description=판매자 상세 설명.
    """

    url: str
    thumbnail_url: str
    area: Literal["gallery", "description"]


class ProductPage(BaseModel):
    """상품 페이지에서 꺼낸 판매자 글과 이미지.

    Attributes:
        source_url: 요청한 상품 페이지 주소.
        site: 판매 사이트 이름 (예: made_in_china).
        title: 상품명.
        text_blocks: 판매자 글 (상품명·사양표 줄·상세 설명 문단). 페이지 순서대로.
        images: 상품 사진 모음과 상세 설명 이미지. 같은 사진은 하나만, 페이지 순서대로.
    """

    source_url: str
    site: str
    title: str | None = None
    text_blocks: list[str] = Field(default_factory=list)
    images: list[ProductPageImage] = Field(default_factory=list)
