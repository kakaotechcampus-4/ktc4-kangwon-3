"""에이전트 연결을 위한 검토용 입출력 초안. BE-AI API 명세 확정본이 아니다."""

from typing import Self

from pydantic import Field, model_validator

from .base import StrictModel
from .schemas import ToolName, ToolResult


class ExtractionInput(StrictModel):
    """추출할 원문 자료. 수집 완료된 자료를 전달받는 방식으로 우선 제안한다."""

    product_id: str = Field(min_length=1)
    # source_url은 출처 표시용이며, URL만으로 페이지를 수집하는 기능은 포함하지 않는다.
    source_url: str | None = None
    text_blocks: list[str] = Field(default_factory=list)
    # 이미지 참조 전달 방식(URL/파일/바이트)은 추출 담당자와 추가 합의가 필요하다.
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


class SelectionResult(StrictModel):
    """선택 에이전트가 반환하는 선택 내역과 실제 실행 기록."""

    selection: ToolSelectionResponse
    # 각 툴의 최신 결과 6개. 미선택 툴도 상태와 이유를 기록한다.
    tool_results: list[ToolResult]
    # 모델이 같은 툴을 다시 호출한 경우를 포함한 실제 실행 이력.
    tool_result_history: list[ToolResult]
