"""결과 상태(result_status) 결정 규칙. 진단 결과만 보고 코드가 정한다 (#310).

값은 BE ResultStatus와 같은 3개이고, 아래 순서로 먼저 맞는 것을 쓴다.
    1. 진단 미완료                                   → RECHECK_REQUIRED (#310: 미완료는 재확인 필요로만)
    2. 인증·허가가 필요할 수 있는 판단이 하나라도 있음  → DIRECT_IMPORT_CERTIFICATION_REQUIRED
    3. 판단 대상 tool 실패, 또는 판단할 정보 부족       → RECHECK_REQUIRED
    4. 그 밖                                        → PURCHASING_AGENT_ALLOWED

- 표시·광고(LABEL_AD)는 판매 방식과 무관한 문구 의무라 결과 상태 계산에서 뺀다. 분야 카드·할 일로만 보여 준다.
- 2를 3보다 먼저 본다. 이미 찾은 인증 요건은 다른 tool의 정보 부족과 상관없이 알려야 한다.
- 위험도 LOW인 정보 부족은 참고 정보로 보고 3에 넣지 않는다.
"""

from dataclasses import dataclass
from enum import StrEnum

from ..schemas.schemas import (
    Determination, ExecutionEndReason, FinalAssessment, FinalVerificationStatus, RegulatoryFinding, RiskLevel,
    ToolName, ToolStatus,
)

# 결과 상태 계산에서 빼는 tool
RESULT_STATUS_EXCLUDED_TOOLS = frozenset({ToolName.LABEL_AD})
_ACTION_DETERMINATIONS = frozenset({Determination.REQUIRED, Determination.POSSIBLY_REQUIRED})
_COMPLETED_VERIFICATION = frozenset({FinalVerificationStatus.VERIFIED, FinalVerificationStatus.VERIFIED_WITH_WARNINGS})


class ResultStatus(StrEnum):
    """BE ResultStatus와 같은 값."""

    PURCHASING_AGENT_ALLOWED = "PURCHASING_AGENT_ALLOWED"
    DIRECT_IMPORT_CERTIFICATION_REQUIRED = "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    RECHECK_REQUIRED = "RECHECK_REQUIRED"


class DecisionReason(StrEnum):
    """결과 상태를 정한 단계. 요약 문장과 안내를 고를 때 씀."""

    INCOMPLETE = "incomplete"
    CERTIFICATION_REQUIRED = "certification_required"
    TOOL_FAILED = "tool_failed"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NO_REQUIREMENT = "no_requirement"
    NO_REGULATED_TOOL = "no_regulated_tool"


@dataclass(frozen=True)
class ResultDecision:
    """결과 상태 결정 결과.

    Attributes:
        status: 결과 상태.
        reason: 결과 상태를 정한 단계.
        tools: 결과 상태를 정한 tool (분야 순서). 미완료·요건 없음이면 빈 튜플.
    """

    status: ResultStatus
    reason: DecisionReason
    tools: tuple[ToolName, ...] = ()


def is_completed(result: FinalAssessment) -> bool:
    """진단이 끝까지 마쳤는지. 검증을 통과(경고 포함)하고 종료 사유가 완료여야 한다."""
    return (result.verification_status in _COMPLETED_VERIFICATION
            and result.termination_reason is ExecutionEndReason.COMPLETED)


def decide_result_status(result: FinalAssessment) -> ResultDecision:
    """진단 결과로 결과 상태를 정한다.

    Args:
        result: 진단 결과.

    Returns:
        ResultDecision: 결과 상태와 그 상태를 정한 단계·tool.
    """
    if not is_completed(result):
        return ResultDecision(ResultStatus.RECHECK_REQUIRED, DecisionReason.INCOMPLETE)

    regulated = [tool for tool in result.selected_tools if tool not in RESULT_STATUS_EXCLUDED_TOOLS]
    if not regulated:
        return ResultDecision(ResultStatus.PURCHASING_AGENT_ALLOWED, DecisionReason.NO_REGULATED_TOOL)
    findings = [finding for finding in result.findings if finding.tool_name in regulated]

    certification = _tools_where(findings, lambda finding: finding.determination in _ACTION_DETERMINATIONS)
    if certification:
        return ResultDecision(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED,
                              DecisionReason.CERTIFICATION_REQUIRED, certification)

    statuses = {item.tool_name: item.status for item in result.tool_results if item.selected}
    failed = tuple(tool for tool in _ordered(regulated) if statuses.get(tool) is not ToolStatus.SUCCESS)
    if failed:
        return ResultDecision(ResultStatus.RECHECK_REQUIRED, DecisionReason.TOOL_FAILED, failed)

    insufficient = _tools_where(findings, _is_blocking_insufficient)
    if insufficient:
        return ResultDecision(ResultStatus.RECHECK_REQUIRED, DecisionReason.INSUFFICIENT_INFORMATION, insufficient)

    return ResultDecision(ResultStatus.PURCHASING_AGENT_ALLOWED, DecisionReason.NO_REQUIREMENT)


def tool_order() -> tuple[ToolName, ...]:
    """분야 카드·할 일을 보여 줄 순서."""
    return tuple(ToolName)


def _ordered(tools) -> tuple[ToolName, ...]:
    wanted = set(tools)
    return tuple(tool for tool in tool_order() if tool in wanted)


def _tools_where(findings: list[RegulatoryFinding], predicate) -> tuple[ToolName, ...]:
    return _ordered({finding.tool_name for finding in findings if predicate(finding)})


def _is_blocking_insufficient(finding: RegulatoryFinding) -> bool:
    """판단할 정보가 부족한 판단. 위험도 LOW인 정보 부족은 참고 정보라 결과 상태에 영향을 주지 않는다."""
    if finding.risk_level is RiskLevel.UNKNOWN:
        return True
    return finding.determination is Determination.INSUFFICIENT_INFORMATION and finding.risk_level is not RiskLevel.LOW
