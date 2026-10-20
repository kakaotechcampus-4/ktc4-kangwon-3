"""규칙 검사 Tool 결과 상태: 실패·빈 결과면 재실행 요구, 결과 종류 불일치 (#64)."""

from app.agents.verification import VerificationAgent
from app.schemas.schemas import (
    RadioAssessment,
    ToolName,
    ToolStatus,
    VerificationIssueType,
    VerificationStatus,
)


def test_선택된_툴이_실패_상태면_재실행을_요구한다(samples):
    draft = samples.draft()
    samples.tool_record(draft, ToolName.ELECTRICAL).status = ToolStatus.FAILED

    result = VerificationAgent().verify_rules(draft)

    assert any(issue.issue_type is VerificationIssueType.TOOL_FAILURE for issue in result.issues)
    assert ToolName.ELECTRICAL in result.additional_tools_required
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_성공한_툴에_상세_결과나_finding이_없으면_재실행을_요구한다(samples):
    draft = samples.draft()
    tool_record = samples.tool_record(draft, ToolName.ELECTRICAL)
    tool_record.result = None
    tool_record.findings = []
    draft.findings = []

    result = VerificationAgent().verify_rules(draft)

    assert any(
        issue.issue_type is VerificationIssueType.TOOL_FAILURE
        and "상세 결과 또는 판단이 없습니다" in issue.description
        for issue in result.issues
    )
    assert ToolName.ELECTRICAL in result.additional_tools_required
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_툴과_상세_결과_kind가_다르면_지적한다(samples):
    draft = samples.draft()
    samples.tool_record(draft, ToolName.ELECTRICAL).result = RadioAssessment()

    result = VerificationAgent().verify_rules(draft)

    assert any("kind가 툴 종류와 다릅니다" in issue.description for issue in result.issues)
