"""결과 상태(result_status) 결정 규칙. 진단 결과만 보고 코드가 정한다 (#310).

값은 BE ResultStatus와 같은 3개이고, 아래 순서로 먼저 맞는 것을 쓴다.
    1. 진단 미완료                                   → RECHECK_REQUIRED (#310: 미완료는 재확인 필요로만)
    2. 인증·허가가 필요할 수 있는 판단이 하나라도 있음  → DIRECT_IMPORT_CERTIFICATION_REQUIRED
    3. 지원 분야 밖 규제 대상일 수 있음                → RECHECK_REQUIRED
    4. 판단 대상 tool이 없음                          → PURCHASING_AGENT_ALLOWED
    5. 판단 대상 tool 실패, 또는 판단할 정보 부족       → RECHECK_REQUIRED
    6. 그 밖                                        → PURCHASING_AGENT_ALLOWED

- 표시·광고(LABEL_AD)는 판매 방식과 무관한 문구 의무라 결과 상태 계산에서 뺀다. 분야 카드·할 일로만 보여 준다.
- 2를 먼저 본다. 이미 찾은 인증 요건은 다른 정보 부족이나 지원 분야 밖 신호와 상관없이 알려야 한다.
- 3은 tool 선택과 상관없이 본다. 화학제품이 통관·식약 tool로 선택돼도 그 tool이 화학제품안전법을 보지 않을 수 있다.
- 정보 부족은 위험도와 상관없이 5에 넣는다. 위험도 표기는 tool마다 달라 규칙이 거기에 기대지 않게 한다.
- 선택된 tool이 SUCCESS인데 판단이 0건이면 6(요건 없음)으로 간다. 근거 조회형 tool은 판단이 없으면
  정보 부족 기본 판단을 내므로 지금은 생기지 않는다. 초안 집계기는 판단 0건을 정보 부족으로 본다.
"""

from dataclasses import dataclass
from enum import StrEnum

from ..schemas.product import Product
from ..schemas.schemas import (
    Determination, ExecutionEndReason, FinalAssessment, FinalVerificationStatus, RegulatoryFinding, RiskLevel,
    ToolName, ToolStatus,
)

# 결과 상태 계산에서 빼는 tool
RESULT_STATUS_EXCLUDED_TOOLS = frozenset({ToolName.LABEL_AD})
# 지원 분야 밖 규제 대상 신호: 추출이 True로 확인한 상품 특성 (None은 신호로 보지 않음)
OUT_OF_SCOPE_SIGNALS = ("chemical_product", "weapon_like", "plant_material")
# 인증·허가가 필요할 수 있는 판단
ACTION_DETERMINATIONS = frozenset({Determination.REQUIRED, Determination.POSSIBLY_REQUIRED})
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
    OUT_OF_SCOPE = "out_of_scope"
    NO_REGULATED_TOOL = "no_regulated_tool"
    TOOL_FAILED = "tool_failed"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NO_REQUIREMENT = "no_requirement"


@dataclass(frozen=True)
class ResultDecision:
    """결과 상태 결정 결과.

    Attributes:
        status: 결과 상태.
        reason: 결과 상태를 정한 단계.
        tools: 결과 상태를 정한 tool (분야 순서). 요건 없음이면 확인한 tool, 미완료·지원 분야 밖·tool 없음이면 빈 튜플.
        signals: 지원 분야 밖 신호 (OUT_OF_SCOPE_SIGNALS 중 True인 것). 결과 상태와 상관없이 채운다.
    """

    status: ResultStatus
    reason: DecisionReason
    tools: tuple[ToolName, ...] = ()
    signals: tuple[str, ...] = ()


def is_completed(result: FinalAssessment) -> bool:
    """진단이 끝까지 마쳤는지. 검증을 통과(경고 포함)하고 종료 사유가 완료여야 한다."""
    return (result.verification_status in _COMPLETED_VERIFICATION
            and result.termination_reason is ExecutionEndReason.COMPLETED)


def out_of_scope_signals(product: Product) -> tuple[str, ...]:
    """지원 분야 밖 규제 대상일 수 있다는 신호. 추출이 True로 확인한 것만."""
    return tuple(name for name in OUT_OF_SCOPE_SIGNALS if getattr(product, name) is True)


def decide_result_status(result: FinalAssessment) -> ResultDecision:
    """진단 결과로 결과 상태를 정한다.

    Args:
        result: 진단 결과.

    Returns:
        ResultDecision: 결과 상태와 그 상태를 정한 단계·tool·지원 분야 밖 신호.
    """
    signals = out_of_scope_signals(result.product)

    def decision(status: ResultStatus, reason: DecisionReason, tools=()) -> ResultDecision:
        return ResultDecision(status, reason, tuple(tools), signals)

    if not is_completed(result):
        return decision(ResultStatus.RECHECK_REQUIRED, DecisionReason.INCOMPLETE)

    regulated = _ordered(tool for tool in result.selected_tools if tool not in RESULT_STATUS_EXCLUDED_TOOLS)
    findings = [finding for finding in result.findings if finding.tool_name in regulated]

    certification = _tools_where(findings, lambda finding: finding.determination in ACTION_DETERMINATIONS)
    if certification:
        return decision(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED, DecisionReason.CERTIFICATION_REQUIRED,
                        certification)
    if signals:
        return decision(ResultStatus.RECHECK_REQUIRED, DecisionReason.OUT_OF_SCOPE)
    if not regulated:
        return decision(ResultStatus.PURCHASING_AGENT_ALLOWED, DecisionReason.NO_REGULATED_TOOL)

    statuses = {item.tool_name: item.status for item in result.tool_results if item.selected}
    failed = tuple(tool for tool in regulated if statuses.get(tool) is not ToolStatus.SUCCESS)
    if failed:
        return decision(ResultStatus.RECHECK_REQUIRED, DecisionReason.TOOL_FAILED, failed)

    insufficient = _tools_where(findings, _is_insufficient)
    if insufficient:
        return decision(ResultStatus.RECHECK_REQUIRED, DecisionReason.INSUFFICIENT_INFORMATION, insufficient)

    return decision(ResultStatus.PURCHASING_AGENT_ALLOWED, DecisionReason.NO_REQUIREMENT, regulated)


def tool_order() -> tuple[ToolName, ...]:
    """분야 카드·할 일을 보여 줄 순서."""
    return tuple(ToolName)


def _ordered(tools) -> tuple[ToolName, ...]:
    wanted = set(tools)
    return tuple(tool for tool in tool_order() if tool in wanted)


def _tools_where(findings: list[RegulatoryFinding], predicate) -> tuple[ToolName, ...]:
    return _ordered({finding.tool_name for finding in findings if predicate(finding)})


def _is_insufficient(finding: RegulatoryFinding) -> bool:
    """판단할 정보가 부족한 판단. 정보 부족 판단이거나 위험도를 판단하지 못한 경우."""
    return finding.determination is Determination.INSUFFICIENT_INFORMATION or finding.risk_level is RiskLevel.UNKNOWN
