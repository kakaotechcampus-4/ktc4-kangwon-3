"""규칙 검사 종합 finding: Tool 원본과 일치·누락·ID 중복·소속 Tool 불일치."""

from app.agents.verification import VerificationAgent
from app.schemas.schemas import ToolName, VerificationIssueType


def test_종합_finding이_툴_원본과_다르면_지적한다(samples):
    draft = samples.draft()
    draft.findings[0].summary = "종합 과정에서 변경된 판단입니다."

    result = VerificationAgent().verify_rules(draft)

    assert any(
        issue.issue_type is VerificationIssueType.CONTRADICTION
        and "원래 툴 판단과 일치하지 않습니다" in issue.description
        for issue in result.issues
    )


def test_툴의_finding이_종합_결과에서_누락되면_지적한다(samples):
    draft = samples.draft()
    draft.findings = []

    result = VerificationAgent().verify_rules(draft)

    descriptions = [issue.description for issue in result.issues]
    assert "검증할 종합 판단이 없습니다." in descriptions
    assert "툴 판단 f1가 종합 결과에서 누락되었습니다." in descriptions


def test_종합_finding_id가_중복되면_지적한다(samples):
    draft = samples.draft()
    draft.findings.append(draft.findings[0].model_copy(deep=True))

    result = VerificationAgent().verify_rules(draft)

    assert any("finding_id가 중복되었습니다" in issue.description for issue in result.issues)


def test_finding의_소속_툴이_실행_기록과_다르면_지적한다(samples):
    draft = samples.draft()
    draft.findings[0].tool_name = ToolName.RADIO
    samples.tool_record(draft, ToolName.ELECTRICAL).findings[0].tool_name = ToolName.RADIO

    result = VerificationAgent().verify_rules(draft)

    assert any("소속 툴 불일치" in issue.description for issue in result.issues)
