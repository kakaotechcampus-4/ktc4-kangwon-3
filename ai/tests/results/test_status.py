"""결과 상태 규칙: 진단 결과 → result_status와 결정 단계를 경우별로 확인한다."""

import pytest

from app.results import ResultStatus, decide_result_status
from app.results.status import DecisionReason
from app.schemas.schemas import Determination, ExecutionEndReason, FinalVerificationStatus, RiskLevel, ToolName, ToolStatus


def test_incomplete_is_recheck(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.RADIO, [finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
        verification_status=FinalVerificationStatus.INCOMPLETE,
        termination_reason=ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
    )

    decision = decide_result_status(result)

    assert (decision.status, decision.reason) == (ResultStatus.RECHECK_REQUIRED, DecisionReason.INCOMPLETE)


def test_certification_required_lists_tools_in_field_order(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CHILDREN, [finding(ToolName.CHILDREN, Determination.POSSIBLY_REQUIRED)]),
        tool_result(ToolName.RADIO, [finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
    )

    decision = decide_result_status(result)

    assert decision.status is ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED
    assert decision.tools == (ToolName.RADIO, ToolName.CHILDREN)


def test_certification_wins_over_insufficient_information(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.ELECTRICAL, [finding(ToolName.ELECTRICAL, Determination.POSSIBLY_REQUIRED)]),
        tool_result(ToolName.CHILDREN, [finding(ToolName.CHILDREN, Determination.INSUFFICIENT_INFORMATION,
                                                RiskLevel.UNKNOWN)]),
    )

    assert decide_result_status(result).status is ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED


@pytest.mark.parametrize("flag", ["chemical_product", "weapon_like", "plant_material"])
def test_out_of_scope_signal_is_recheck_even_with_selected_tools(assessment, tool_result, finding, flag):
    # 화학제품이 통관 tool로 선택돼도 통관이 요건을 못 찾으면 구매대행 가능으로 빠지지 않게
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        product_flags={flag: True},
    )

    decision = decide_result_status(result)

    assert (decision.status, decision.reason) == (ResultStatus.RECHECK_REQUIRED, DecisionReason.OUT_OF_SCOPE)
    assert decision.signals == (flag,)


def test_out_of_scope_signal_without_selected_tools_is_recheck(assessment):
    decision = decide_result_status(assessment(product_flags={"chemical_product": True}))

    assert decision.reason is DecisionReason.OUT_OF_SCOPE


def test_certification_wins_over_out_of_scope_but_keeps_signal(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.POSSIBLY_REQUIRED)]),
        product_flags={"chemical_product": True},
    )

    decision = decide_result_status(result)

    assert decision.reason is DecisionReason.CERTIFICATION_REQUIRED
    assert decision.signals == ("chemical_product",)


@pytest.mark.parametrize("value", [False, None])
def test_unconfirmed_signal_is_ignored(assessment, tool_result, finding, value):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        product_flags={"chemical_product": value, "weapon_like": value, "plant_material": value},
    )

    assert decide_result_status(result).reason is DecisionReason.NO_REQUIREMENT


def test_failed_tool_is_recheck(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        tool_result(ToolName.RADIO, status=ToolStatus.FAILED),
    )

    decision = decide_result_status(result)

    assert (decision.reason, decision.tools) == (DecisionReason.TOOL_FAILED, (ToolName.RADIO,))


def test_selected_tool_without_record_counts_as_failed(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        selected_tools=[ToolName.CUSTOMS, ToolName.RADIO],
    )

    assert decide_result_status(result).tools == (ToolName.RADIO,)


@pytest.mark.parametrize(("determination", "risk"), [
    (Determination.INSUFFICIENT_INFORMATION, RiskLevel.MEDIUM),
    # 위험도 LOW여도 정보 부족은 재확인 (관세의 근거 법령 조회 실패가 LOW로 나옴)
    (Determination.INSUFFICIENT_INFORMATION, RiskLevel.LOW),
    (Determination.NOT_REQUIRED, RiskLevel.UNKNOWN),
])
def test_insufficient_information_is_recheck(assessment, tool_result, finding, determination, risk):
    result = assessment(
        tool_result(ToolName.ELECTRICAL, [finding(ToolName.ELECTRICAL, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, determination, risk)]),
    )

    decision = decide_result_status(result)

    assert (decision.reason, decision.tools) == (DecisionReason.INSUFFICIENT_INFORMATION, (ToolName.CUSTOMS,))


def test_no_requirement_lists_checked_tools(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.ELECTRICAL, [finding(ToolName.ELECTRICAL, Determination.NOT_APPLICABLE, RiskLevel.LOW)]),
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
    )

    decision = decide_result_status(result)

    assert decision.status is ResultStatus.PURCHASING_AGENT_ALLOWED
    assert (decision.reason, decision.tools) == (DecisionReason.NO_REQUIREMENT, (ToolName.CUSTOMS, ToolName.ELECTRICAL))


def test_label_ad_only_counts_as_no_regulated_tool(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.LABEL_AD, [finding(ToolName.LABEL_AD, Determination.POSSIBLY_REQUIRED, RiskLevel.HIGH)]),
    )

    decision = decide_result_status(result)

    assert (decision.status, decision.reason) == (ResultStatus.PURCHASING_AGENT_ALLOWED,
                                                  DecisionReason.NO_REGULATED_TOOL)
