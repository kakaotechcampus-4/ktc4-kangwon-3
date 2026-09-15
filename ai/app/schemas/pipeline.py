"""파이프라인 실행 및 재실행에 사용하는 내부 계약."""

from pydantic import Field

from .base import StrictModel
from .schemas import ToolName, ToolResult, VerificationResult


class RetryRequest(StrictModel):
    """Verification 결과에 따라 Pipeline이 생성하는 Tool 재실행 요청."""

    attempt: int = Field(ge=1)
    requested_tools: list[ToolName] = Field(min_length=1)
    verification: VerificationResult
    latest_tool_results: list[ToolResult]