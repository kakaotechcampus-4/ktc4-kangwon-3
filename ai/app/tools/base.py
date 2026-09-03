"""심사 툴 6개가 따를 공통 호출 규격."""

from abc import ABC, abstractmethod
from typing import ClassVar

from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Product
from ..schemas.schemas import ToolName, ToolResult


class RegulatoryTool(ABC):
    """기관 클라이언트로 자료를 조회하고 ToolResult로 심사 결과를 반환한다."""

    tool_name: ClassVar[ToolName]

    @abstractmethod
    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """상품 정보와 이 툴의 선택 결정을 받는다. 실제 구현은 각 툴에 둔다."""
        # 구현 시 decision.tool_name이 해당 툴인지 확인하고 미선택 시 호출을 생략한다.
        # 조회 실패를 규제 비대상으로 바꾸지 않으며, 선택 이유도 결과에 보존한다.
        raise NotImplementedError
