"""에이전트 연결을 위한 검토용 입출력 초안. BE-AI API 명세 확정본이 아니다."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from .base import StrictModel
from .schemas import ToolName


class ExtractionInput(StrictModel):
    """추출할 원문 자료. 수집 완료된 자료를 전달받는 방식으로 우선 제안한다."""

    product_id: str = Field(min_length=1)
    # source_url은 출처 표시용이며, URL만으로 페이지를 수집하는 기능은 포함하지 않는다.
    source_url: str | None = None
    text_blocks: list[str] = Field(default_factory=list)
    # 2026-09-06 결정: http(s) URL과 data:image/...;base64,... 문자열을 모두 받는다.
    # 로컬 이미지(테스트 픽스처 등)는 호출자가 data URI로 인코딩해서 넣는다.
    # 별도 바이트 필드를 두지 않은 이유: OpenAI vision API가 두 형식을 동일하게 처리한다.
    image_urls: list[str] = Field(default_factory=list)


class ToolSelectionItem(StrictModel):
    """툴 하나의 선택 여부와 이유. 선택 여부와 실행 성공 여부는 다르다."""

    tool_name: ToolName
    selected: bool
    reason: str = Field(min_length=1)


class ToolSelectionResponse(StrictModel):
    """미선택 툴도 이유와 함께 기록하는 6개 툴 선택 목록."""

    decisions: list[ToolSelectionItem]

    @model_validator(mode="after")
    def require_all_tools_once(self) -> Self:
        # 기존 프로토타입의 중복·누락 검사를 공통 규격으로 옮긴다.
        names = [item.tool_name for item in self.decisions]
        if len(names) != len(ToolName) or set(names) != set(ToolName):
            raise ValueError("선택 결과에는 6개 심사 툴이 각각 한 번씩 있어야 합니다.")
        return self

class ImageCategory(StrEnum):
    """상품 페이지 이미지 분류. 사양·인증·포장은 추출에 쓸 글자가 있는 사진."""

    SPECIFICATION = "specification"  # 정격·용량·사양이 적힌 표나 글자
    CERTIFICATION = "certification"  # 인증 마크·라벨·명판·경고 문구·시험 성적서
    PACKAGE = "package"  # 포장 상자·설명서의 글자 (연령, 구성품 등)
    PRODUCT = "product"  # 글자가 거의 없는 제품 사진
    LIFESTYLE = "lifestyle"  # 사용 장면·모델 연출 사진
    UNRELATED = "unrelated"  # 다른 상품, 회사·배송 안내, 연락처 배너, 아이콘


class ImageTriageItem(StrictModel):
    """이미지 하나의 분류. index는 입력 순서 (1부터)."""

    index: int = Field(ge=1)
    category: ImageCategory


class ImageTriageResponse(StrictModel):
    """후보 이미지 분류 결과. 같은 번호는 한 번만."""

    items: list[ImageTriageItem]

    @model_validator(mode="after")
    def unique_indexes(self) -> Self:
        indexes = [item.index for item in self.items]
        if len(indexes) != len(set(indexes)):
            raise ValueError("같은 이미지 번호를 두 번 분류할 수 없습니다.")
        return self
