"""식약 심사 담당자의 구현 위치."""

from .base import RegulatoryTool
from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Product
from ..schemas.schemas import ToolName, ToolResult


class FoodDrugTool(RegulatoryTool):
    tool_name = ToolName.FOOD_DRUG

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        # TODO: 용도·접촉 대상·표방 문구·성분을 검토하고 FoodDrugAssessment를 result에 담는다.
        # 상품 신호만으로 규제 적용을 확정하지 않는다. 실제 근거 조회는 후속 구현이다.
        raise NotImplementedError("식약 심사 로직은 아직 구현되지 않았습니다.")
