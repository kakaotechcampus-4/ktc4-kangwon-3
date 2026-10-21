"""규칙 검사 상품 신호: 명시적 신호(is True)에 필요한 Tool 누락, 연령 표기와 어린이 대상 판단 (#165)."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.product import Product
from app.schemas.schemas import ToolName, VerificationIssueType, VerificationStatus


@pytest.mark.parametrize(
    ("attribute", "expected_tool"),
    [
        ("wireless_comm", ToolName.RADIO),
        ("wireless_charging", ToolName.RADIO),
        ("electrical_powered", ToolName.ELECTRICAL),
        ("battery_included", ToolName.ELECTRICAL),
        ("battery_is_the_product", ToolName.ELECTRICAL),
        ("for_children", ToolName.CHILDREN),
        ("food_contact", ToolName.FOOD_DRUG),
        ("medical_claim", ToolName.FOOD_DRUG),
        ("cosmetic_claim", ToolName.FOOD_DRUG),
    ],
)
def test_상품의_명시적_신호에_필요한_툴이_없으면_지적한다(
    samples,
    attribute: str,
    expected_tool: ToolName,
):
    product = Product(product_id="p1", **{attribute: True})
    draft = samples.draft(product)
    samples.unselect_tool(draft, expected_tool)

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.TOOLS_REQUIRED
    assert expected_tool in result.additional_tools_required
    issue = next(
        issue
        for issue in result.issues
        if issue.issue_type is VerificationIssueType.MISSING_TOOL
        and issue.description.startswith(f"{expected_tool}:")
    )
    assert issue.severity == "warning"


@pytest.mark.parametrize("signal", [False, None])
def test_명시적_상품_신호가_아니면_필수_툴_누락으로_지적하지_않는다(samples, signal):
    product = Product(
        product_id="p1",
        wireless_comm=signal,
        wireless_charging=signal,
        electrical_powered=signal,
        battery_included=signal,
        battery_is_the_product=signal,
        for_children=signal,
        food_contact=signal,
        medical_claim=signal,
        cosmetic_claim=signal,
    )
    draft = samples.draft(product)
    samples.unselect_tool(draft, ToolName.ELECTRICAL)

    result = VerificationAgent().verify_rules(draft)

    assert not any(
        issue.issue_type is VerificationIssueType.MISSING_TOOL
        and "상품에 검토 신호가 있으나" in issue.description
        for issue in result.issues
    )


def test_연령_표기가_있는데_어린이_대상_판단이_없으면_지적한다(samples):
    draft = samples.draft(Product(product_id="p1", target_age="만 3세 이상"))

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.APPROVED_WITH_WARNINGS
    issue = next(
        issue for issue in result.issues
        if issue.issue_type.value == "insufficient_product_data"
    )
    assert issue.severity == "warning"
    # 같은 입력으로 툴을 다시 돌려도 결과가 같으므로 재실행을 요구하지 않는다.
    assert ToolName.CHILDREN not in result.additional_tools_required


def test_어린이_대상_여부가_판단된_상품은_지적하지_않는다(samples):
    # for_children=False는 판단이 끝난 상태이므로 연령 표기가 있어도 통과한다.
    draft = samples.draft(Product(product_id="p1", target_age="만 14세 이상", for_children=False))

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.APPROVED
