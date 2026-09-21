"""6개 심사 결과를 검증용 초안으로 조립한다."""

from collections.abc import Iterable

from ..schemas.agent import SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import (
    Determination,
    DraftAssessment,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolResult,
    ToolStatus,
)


class ResultAggregator:
    """Tool 결과에 없는 판단을 생성하지 않고 초안으로 조립한다."""

    def aggregate(
        self,
        product: Product,
        selection_result: SelectionResult,
    ) -> DraftAssessment:
        """최신 Tool 결과를 복사해 검증 전 DraftAssessment를 만든다."""
        tool_results = [
            result.model_copy(deep=True) for result in selection_result.tool_results
        ]
        findings = [
            finding.model_copy(deep=True)
            for result in tool_results
            for finding in result.findings
        ]
        required_actions = self._unique(
            action for result in tool_results for action in result.required_actions
        )
        missing_information = self._unique(
            item for result in tool_results for item in result.missing_information
        )
        assumptions = self._unique(
            assumption for finding in findings for assumption in finding.assumptions
        )
        selected_tools = [
            decision.tool_name
            for decision in selection_result.selection.decisions
            if decision.selected
        ]
        overall_status = self._overall_status(
            tool_results,
            findings,
            required_actions,
            missing_information,
        )
        completed_count = sum(
            result.selected and result.status is ToolStatus.SUCCESS
            for result in tool_results
        )
        incomplete_count = len(selected_tools) - completed_count

        return DraftAssessment(
            product=product.model_copy(deep=True),
            selected_tools=selected_tools,
            tool_results=tool_results,
            findings=findings,
            overall_status=overall_status,
            summary=(
                f"선택 Tool {len(selected_tools)}개 중 성공 {completed_count}개, "
                f"미완료 {incomplete_count}개이며 판단 {len(findings)}건을 "
                "수집했습니다."
            ),
            required_actions=required_actions,
            missing_information=missing_information,
            follow_up_questions=[],
            assumptions=assumptions,
        )

    @staticmethod
    def _overall_status(
        tool_results: list[ToolResult],
        findings: list[RegulatoryFinding],
        required_actions: list[str],
        missing_information: list[str],
    ) -> OverallStatus:
        """확인된 위험을 숨기지 않고, 그 다음으로 조치·정보 부족을 표시한다."""
        if any(finding.risk_level is RiskLevel.HIGH for finding in findings):
            return OverallStatus.HIGH_RISK

        action_determinations = {
            Determination.REQUIRED,
            Determination.POSSIBLY_REQUIRED,
        }
        if (
            required_actions
            or any(
                finding.determination in action_determinations
                for finding in findings
            )
            or any(finding.risk_level is RiskLevel.MEDIUM for finding in findings)
        ):
            return OverallStatus.ACTION_REQUIRED

        has_incomplete_tool = any(
            result.selected and result.status is not ToolStatus.SUCCESS
            for result in tool_results
        )
        has_incomplete_finding = any(
            finding.determination is Determination.INSUFFICIENT_INFORMATION
            or finding.risk_level is RiskLevel.UNKNOWN
            for finding in findings
        )
        if has_incomplete_tool or missing_information or has_incomplete_finding or not findings:
            return OverallStatus.INSUFFICIENT_INFORMATION

        return OverallStatus.LIKELY_COMPLIANT

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        """최초 등장 순서를 유지하며 중복 문자열을 제거한다."""
        return list(dict.fromkeys(values))
