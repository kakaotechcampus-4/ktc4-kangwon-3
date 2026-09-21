"""PipelineManaged 방식의 규제 Tool 실행 경계."""

from collections.abc import Mapping
from uuid import uuid4

from ..schemas.agent import ToolSelectionItem, ToolSelectionResponse
from ..schemas.pipeline import SelectionResult
from ..schemas.base import utc_now
from ..schemas.product import Product
from ..schemas.schemas import ToolName, ToolResult, ToolStatus
from ..tools.base import RegulatoryTool


class ToolExecutor:
    """선택 결정에 따라 규제 Tool을 실행하고 공통 실행 정보를 부여한다."""

    def __init__(self, tools: Mapping[ToolName, RegulatoryTool]) -> None:
        if set(tools) != set(ToolName):
            raise ValueError("6개 규제 Tool 구현이 모두 필요합니다.")
        if any(tool.tool_name != name for name, tool in tools.items()):
            raise ValueError("등록한 Tool 이름과 구현의 tool_name이 다릅니다.")
        self._tools = dict(tools)

    def execute_initial(
        self,
        product: Product,
        selection: ToolSelectionResponse,
    ) -> SelectionResult:
        """최초 선택 결과 6개를 실행 또는 건너뛰고 실행 기록을 만든다."""
        tool_results = [
            self._execute_one(product, decision, retry_round=0)
            for decision in selection.decisions
        ]
        history = [
            result.model_copy(deep=True)
            for result in tool_results
            if result.status is not ToolStatus.SKIPPED
        ]
        return SelectionResult(
            selection=selection.model_copy(deep=True),
            tool_results=[result.model_copy(deep=True) for result in tool_results],
            tool_result_history=history,
        )

    def _execute_one(
        self,
        product: Product,
        decision: ToolSelectionItem,
        *,
        retry_round: int = 0,
    ) -> ToolResult:
        """Tool 하나를 실행하고 실행 실패도 ToolResult로 보존한다."""
        if retry_round < 0:
            raise ValueError("retry_round는 0 이상이어야 합니다.")

        if not decision.selected:
            return ToolResult(
                tool_name=decision.tool_name,
                status=ToolStatus.SKIPPED,
                selected=False,
                selection_reason=decision.reason,
                retry_round=retry_round,
            )

        execution_id = str(uuid4())
        started_at = utc_now()
        try:
            result = ToolResult.model_validate(
                self._tools[decision.tool_name].execute(
                    product.model_copy(deep=True),
                    decision.model_copy(deep=True),
                )
            ).model_copy(deep=True)
            if result.tool_name != decision.tool_name:
                raise ValueError("실행한 Tool과 반환 결과의 tool_name이 다릅니다.")
            if not result.selected or result.status is ToolStatus.SKIPPED:
                raise ValueError("선택해 실행한 Tool이 미선택 결과를 반환했습니다.")
        except Exception as exc:
            return ToolResult(
                execution_id=execution_id,
                retry_round=retry_round,
                tool_name=decision.tool_name,
                status=ToolStatus.FAILED,
                selected=True,
                selection_reason=decision.reason,
                error=f"{type(exc).__name__}: Tool 실행에 실패했습니다.",
                executed_at=started_at,
            )

        return result.model_copy(
            update={
                "execution_id": execution_id,
                "retry_round": retry_round,
                "selection_reason": decision.reason,
                "executed_at": started_at,
            },
            deep=True,
        )
