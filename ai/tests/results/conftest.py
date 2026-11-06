"""결과 종합 테스트 공용 진단 결과 만들기. 더미 결과의 상품·검증을 빌려 tool 결과만 바꾼다."""

import pytest

from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import FinalAssessment, RegulatoryFinding, RiskLevel, ToolResult, ToolStatus


@pytest.fixture
def finding():
    """판단 하나. 제목·요약·근거는 기본값, extra로 덮어씀."""
    def make(tool, determination, risk=RiskLevel.MEDIUM, **extra) -> RegulatoryFinding:
        values = dict(subject=f"{tool.name} 판단", summary="요약", rationale="근거")
        values.update(extra)
        return RegulatoryFinding(tool_name=tool, determination=determination, risk_level=risk, **values)
    return make


@pytest.fixture
def tool_result():
    """선택된 tool의 실행 기록 하나."""
    def make(tool, findings=(), status=ToolStatus.SUCCESS, actions=(), missing=()) -> ToolResult:
        return ToolResult(
            tool_name=tool, status=status, selected=True, selection_reason="선택",
            findings=list(findings), required_actions=list(actions), missing_information=list(missing),
        )
    return make


@pytest.fixture
def assessment():
    """tool 결과로 만든 완료 진단 결과. product_flags로 상품 특성을, changes로 진단 결과 칸을 바꿈."""
    def make(*tool_results: ToolResult, product_flags: dict | None = None, **changes) -> FinalAssessment:
        base = build_dummy_assessment("prod-1")
        values = dict(
            product=base.product.model_copy(update=product_flags or {}),
            selected_tools=[item.tool_name for item in tool_results],
            tool_results=list(tool_results),
            findings=[item for result in tool_results for item in result.findings],
            required_actions=[],
            missing_information=[],
        )
        values.update(changes)
        return base.model_copy(update=values)
    return make
