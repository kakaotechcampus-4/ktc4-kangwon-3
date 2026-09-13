"""전안법 심사 담당자의 구현 위치."""

from .base import RegulatoryTool
from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Product
from ..schemas.schemas import ToolName, ToolResult


class ElectricalTool(RegulatoryTool):
    tool_name = ToolName.ELECTRICAL

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        # TODO: 전원·배터리·발열 등 상품 특성을 검토하고 ElectricalAssessment를 result에 담는다.
        # 상품 신호만으로 규제 적용을 확정하지 않는다. 실제 근거 조회는 후속 구현이다.
        raise NotImplementedError("전안법 심사 로직은 아직 구현되지 않았습니다.")
