"""규칙 검사 Tool 실행 기록: 누락·중복·선택 불일치·미선택 Tool 결과 (#64, #153)."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.schemas import (
    Determination,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolStatus,
    VerificationIssueType,
    VerificationStatus,
)


def test_규칙_검사는_모델_없이도_동작한다(samples):
    result = VerificationAgent().verify_rules(samples.draft())

    assert result.status is VerificationStatus.APPROVED
    assert result.issues == []
    # 의미 검토를 하지 않았으므로 검토한 판단 ID를 채우지 않는다.
    assert result.checked_finding_ids == []


def test_픽스처의_툴_원본과_종합_finding은_서로_독립적이다(samples):
    draft = samples.draft()

    assert draft.findings[0] == draft.tool_results[-1].findings[0]
    assert draft.findings[0] is not draft.tool_results[-1].findings[0]


def test_툴_실행_기록이_누락되면_지적한다(samples):
    draft = samples.draft()
    draft.tool_results = [
        result for result in draft.tool_results if result.tool_name is not ToolName.RADIO
    ]

    result = VerificationAgent().verify_rules(draft)

    assert any(
        issue.issue_type is VerificationIssueType.MISSING_TOOL
        and "실행 기록이 없습니다" in issue.description
        for issue in result.issues
    )


def test_툴_실행_기록과_선택_목록의_중복을_각각_지적한다(samples):
    draft = samples.draft()
    draft.tool_results.append(draft.tool_results[0].model_copy(deep=True))
    draft.selected_tools.append(ToolName.ELECTRICAL)

    result = VerificationAgent().verify_rules(draft)

    descriptions = [issue.description for issue in result.issues]
    assert "같은 툴의 실행 기록이 중복되었습니다." in descriptions
    assert "선택 툴 목록에 중복이 있습니다." in descriptions


def test_selected와_선택_목록이_다르면_지적한다(samples):
    draft = samples.draft()
    samples.tool_record(draft, ToolName.RADIO).selected = True

    result = VerificationAgent().verify_rules(draft)

    assert any("selected가 다릅니다" in issue.description for issue in result.issues)


def test_미선택_툴에_실행_결과가_있으면_모순으로_지적한다(samples):
    draft = samples.draft()
    unselected = next(record for record in draft.tool_results if not record.selected)
    unselected.status = ToolStatus.SUCCESS
    unselected.findings = [
        RegulatoryFinding(
            finding_id="stale-finding",
            tool_name=unselected.tool_name,
            subject="실행되면 안 되는 판단",
            determination=Determination.POSSIBLY_REQUIRED,
            risk_level=RiskLevel.UNKNOWN,
            summary="미선택 상태와 모순됩니다.",
            rationale="테스트 데이터입니다.",
        )
    ]

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.REVISION_REQUIRED
    assert any("미선택 툴" in issue.description for issue in result.issues)


@pytest.mark.parametrize(
    "tool_name",
    list(ToolName),
    ids=lambda tool_name: tool_name.value,
)
def test_선택된_툴의_실행_기록이_누락되면_revision_required가_된다(
    samples,
    tool_name: ToolName,
):
    draft = samples.draft()

    # 기본 픽스처의 ELECTRICAL 실행 결과와 종합 finding을 제거해
    # 모든 Tool이 미선택된 일관된 상태로 만든다.
    samples.unselect_tool(draft, ToolName.ELECTRICAL)

    # 검사할 Tool을 선택 목록에는 남기고 실행 기록만 제거한다.
    draft.selected_tools = [tool_name]
    draft.tool_results = [
        result
        for result in draft.tool_results
        if result.tool_name is not tool_name
    ]

    result = VerificationAgent().verify_rules(draft)

    issue = next(
        issue
        for issue in result.issues
        if issue.issue_type is VerificationIssueType.MISSING_TOOL
        and issue.description.startswith(f"{tool_name}:")
        and "실행 기록이 없습니다" in issue.description
    )

    assert issue.severity == "critical"
    assert tool_name in result.additional_tools_required
    assert result.status is VerificationStatus.REVISION_REQUIRED
