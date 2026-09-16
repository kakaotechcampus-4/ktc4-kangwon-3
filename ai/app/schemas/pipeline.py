"""파이프라인 실행 및 재실행에 사용하는 내부 계약."""

from pydantic import Field

from .base import StrictModel
from .schemas import ToolName, ToolResult, VerificationResult
from .agent import ToolSelectionResponse


class RetryRequest(StrictModel):
    """Verification 결과에 따라 Pipeline이 생성하는 Tool 재실행 요청."""

    # 재실행 회차를 나타낸다. 첫 번째 재실행부터 1을 사용한다.
    retry_round: int = Field(ge=1)

    # Verification Agent의 요청을 바탕으로 Pipeline이 이번 회차에 실제 실행하기로 한 툴의 목록이다.
    # 현재 정책에서는 verification.additional_tools_required와 동일하다.
    requested_tools: list[ToolName] = Field(min_length=1)

    verification: VerificationResult
    latest_tool_results: list[ToolResult]

class SelectionResult(StrictModel):
    """Tool Executor가 반환하는 선택 내역과 실제 실행 기록."""

    selection: ToolSelectionResponse
    # 각 툴의 최신 결과 6개. 미선택 툴도 상태와 이유를 기록한다.
    tool_results: list[ToolResult]
    # 모델이 같은 툴을 다시 호출한 경우를 포함한 실제 실행 이력.
    tool_result_history: list[ToolResult]
