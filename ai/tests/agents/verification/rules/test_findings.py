"""규칙 검사 종합 finding: Tool 원본과 일치·누락·ID 중복·소속 Tool 불일치."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.schemas import ToolName, VerificationIssueType, VerificationStatus


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


def _set_summary(samples, draft, summary: str) -> None:
    """f1의 요약을 종합 목록과 Tool 기록 양쪽에서 바꾼다 (규칙 검사의 일치 요구)."""
    draft.findings[0].summary = summary
    for finding in samples.tool_record(draft, draft.findings[0].tool_name).findings:
        if finding.finding_id == draft.findings[0].finding_id:
            finding.summary = summary


@pytest.mark.parametrize("summary", [
    "전기용품 안전관리 대상이 아니어서 인증 없이 판매할 수 있습니다.",
    "문제 없는 표현이라 고칠 필요가 없습니다.",
    "무선 기능이 없는 유선 이어폰으로 보여 적합성평가 대상이 아닐 가능성이 큽니다.",
    "만 14세 이상용 제품이라 어린이제품 안전관리 대상이 아닙니다.",
])
def test_가능성_있음_판정인데_요약이_필요_없다고_안내하면_막는다(samples, summary):
    # 검증 튜닝 held-out 결함: 판정은 가능성 있음 그대로, 요약만 "필요 없음"으로 바뀐 판단
    draft = samples.draft()
    _set_summary(samples, draft, summary)

    result = VerificationAgent().verify_rules(draft)

    issue = next(issue for issue in result.issues if "요약은 필요 없다고 안내합니다" in issue.description)
    assert issue.severity == "critical" and issue.issue_type is VerificationIssueType.CONTRADICTION
    assert issue.related_finding_ids == [draft.findings[0].finding_id]
    assert result.status is VerificationStatus.REVISION_REQUIRED


@pytest.mark.parametrize("summary", [
    "이 품목으로 분류되면 안전확인대상 전기용품일 가능성이 있습니다(확정 아님).",
    "- 품목번호: HS 3924.10-0000 후보\n- 미리 갖출 서류: 수입식품등 수입신고확인증",
    # 야생생물법 조건 문구: 가능성 있음 판단 요약에 붙음
    "- 품목번호: HS 4202.31-1090 후보\n- 악어·뱀 등 멸종위기종(CITES) 가죽이나 부위를 쓴 제품에만 해당하고, "
    "소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다.",
    "- 품목번호: HS 3307.49-0000 후보\n- 의약품·의약외품·한약재·동물용 의약품에 해당하는 물품에만 해당합니다.",
    "원재료나 성분을 내세운 주장입니다.",
])
def test_지금_Tool이_가능성_있음_판단에_쓰는_요약은_막지_않는다(samples, summary):
    draft = samples.draft()
    _set_summary(samples, draft, summary)

    result = VerificationAgent().verify_rules(draft)

    assert not any("요약은 필요 없다고 안내합니다" in issue.description for issue in result.issues)
