"""규칙 검사 근거: 확정적 판단은 실자료 인용문과 출처가 있어야 함. 없으면 critical, mock뿐이면 경고."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.schemas import Determination, ToolName, VerificationIssueType, VerificationStatus


def test_확정적_판단에_근거가_아예_없으면_critical로_지적한다(samples):
    draft = samples.draft()
    # legal_sources가 비어 있는 상태로 확정 판단만 바꾼다.
    draft.findings[0].determination = Determination.REQUIRED
    draft.tool_results[-1].findings[0].determination = Determination.REQUIRED

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.TOOLS_REQUIRED
    issue = next(i for i in result.issues if i.issue_type.value == "missing_evidence")
    assert issue.severity == "critical"
    assert "인용문과 출처가 없습니다" in issue.description


def test_확정적_판단의_근거가_mock뿐이면_경고로_낮춘다(samples):
    draft = samples.draft()
    source = samples.law_source(is_mock=True)
    for finding in (draft.findings[0], draft.tool_results[-1].findings[0]):
        finding.determination = Determination.REQUIRED
        finding.legal_sources = [source]

    result = VerificationAgent().verify_rules(draft)

    issue = next(i for i in result.issues if i.issue_type.value == "missing_evidence")
    assert issue.severity == "warning"
    assert "mock" in issue.description
    # 툴을 다시 돌려도 mock 여부는 바뀌지 않으므로 재실행을 요구하지 않는다.
    assert ToolName.ELECTRICAL not in result.additional_tools_required
    assert result.status is VerificationStatus.APPROVED_WITH_WARNINGS


def test_확정적_판단에_실자료_근거가_있으면_통과한다(samples):
    draft = samples.draft()
    source = samples.law_source()
    for finding in (draft.findings[0], samples.tool_record(draft, ToolName.ELECTRICAL).findings[0]):
        finding.determination = Determination.REQUIRED
        finding.legal_sources = [source.model_copy(deep=True)]

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.APPROVED
    assert not any(
        issue.issue_type is VerificationIssueType.MISSING_EVIDENCE
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("quoted_text", "source_url"),
    [
        ("안전확인신고를 하여야 한다.", None),
        (None, "https://www.law.go.kr/"),
    ],
)
def test_확정적_판단의_인용문과_URL_중_하나라도_없으면_근거_부족이다(
    samples,
    quoted_text: str | None,
    source_url: str | None,
):
    draft = samples.draft()
    source = samples.law_source(law_name=None, article=None, quoted_text=quoted_text, source_url=source_url)
    for finding in (draft.findings[0], samples.tool_record(draft, ToolName.ELECTRICAL).findings[0]):
        finding.determination = Determination.REQUIRED
        finding.legal_sources = [source.model_copy(deep=True)]

    result = VerificationAgent().verify_rules(draft)

    issue = next(
        issue
        for issue in result.issues
        if issue.issue_type is VerificationIssueType.MISSING_EVIDENCE
    )
    assert issue.severity == "critical"
    assert result.status is VerificationStatus.TOOLS_REQUIRED
