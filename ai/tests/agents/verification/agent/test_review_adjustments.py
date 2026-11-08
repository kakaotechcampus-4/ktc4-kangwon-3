"""모델 검토 응답의 코드 후처리 (#652).

불확실 판단만 가리키는 치명 지적은 경고로 낮추고, 이미 성공한 Tool의 재실행 요청은 뺀다.
규칙 검사의 지적·재실행 요청은 건드리지 않는다.
"""

from app.agents.verification import VerificationAgent
from app.agents.verification.schemas import _Issue
from app.schemas.schemas import (
    Determination,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolStatus,
    VerificationStatus,
)


def _issue(issue_type: str, ids: list[str], severity: str = "critical") -> _Issue:
    return _Issue(severity=severity, issue_type=issue_type, description="근거가 부족합니다.",
                  related_finding_ids=ids, recommended_action=None)


def _add_definitive_finding(samples, draft, legal_sources) -> None:
    """확정 판단 f2를 Tool 기록과 종합 목록 양쪽에 넣는다 (규칙 검사의 일치 요구)."""
    finding = RegulatoryFinding(
        finding_id="f2", tool_name=ToolName.ELECTRICAL, subject="안전확인 대상",
        determination=Determination.REQUIRED, risk_level=RiskLevel.HIGH,
        summary="안전확인 대상입니다.", rationale="품목표에 해당합니다.", legal_sources=legal_sources,
    )
    samples.tool_record(draft, ToolName.ELECTRICAL).findings.append(finding)
    draft.findings.append(finding.model_copy(deep=True))


def test_불확실_판단만_가리키는_치명_지적은_경고로_낮춘다(samples, stub_model, records):
    # 기본 초안의 f1은 possibly_required
    review = samples.review(issues=[_issue("missing_evidence", ["f1"])])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    [issue] = result.issues
    assert issue.severity == "warning"
    assert result.status is VerificationStatus.APPROVED_WITH_WARNINGS


def test_확정_판단을_가리키는_치명_지적은_그대로_둔다(samples, stub_model, records):
    draft = samples.draft()
    _add_definitive_finding(samples, draft, [samples.law_source()])
    review = samples.review(issues=[_issue("unsupported_claim", ["f2"])], checked_finding_ids=["f1", "f2"])

    result = VerificationAgent(stub_model(review)).run(draft)

    [issue] = result.issues
    assert issue.severity == "critical"
    assert result.status is VerificationStatus.REVISION_REQUIRED


def test_불확실과_확정을_같이_가리키는_치명_지적은_낮추지_않는다(samples, stub_model, records):
    draft = samples.draft()
    _add_definitive_finding(samples, draft, [samples.law_source()])
    review = samples.review(issues=[_issue("missing_evidence", ["f1", "f2"])], checked_finding_ids=["f1", "f2"])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert [issue.severity for issue in result.issues] == ["critical"]


def test_판단을_가리키지_않는_치명_지적은_낮추지_않는다(samples, stub_model, records):
    review = samples.review(issues=[_issue("missing_evidence", [])])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    [issue] = result.issues
    assert issue.severity == "critical"


def test_모순_지적은_불확실_판단을_가리켜도_그대로_둔다(samples, stub_model, records):
    review = samples.review(issues=[_issue("contradiction", ["f1"])])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    [issue] = result.issues
    assert issue.severity == "critical"
    assert result.status is VerificationStatus.REVISION_REQUIRED


def test_규칙_검사의_치명_지적과_재실행_요청은_유지한다(samples, stub_model, records):
    # 확정 판단 f2에 근거가 없음 → 규칙 검사가 치명 지적 + electrical 재실행 요청 (성공한 Tool이어도)
    draft = samples.draft()
    _add_definitive_finding(samples, draft, [])
    review = samples.review(checked_finding_ids=["f1", "f2"])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert any(issue.severity == "critical" for issue in result.issues)
    assert ToolName.ELECTRICAL in result.additional_tools_required
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_이미_성공한_Tool의_모델_재실행_요청은_뺀다(samples, stub_model, records):
    review = samples.review(additional_tools_required=[ToolName.ELECTRICAL])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert result.additional_tools_required == []
    assert result.status is not VerificationStatus.TOOLS_REQUIRED


def test_선택되지_않았던_Tool의_재실행_요청은_남긴다(samples, stub_model, records):
    review = samples.review(additional_tools_required=[ToolName.RADIO])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert result.additional_tools_required == [ToolName.RADIO]
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_실패한_Tool의_재실행_요청은_남긴다(samples):
    # 규칙 검사를 거치지 않고 후처리만 본다 (실패 Tool은 규칙 검사도 재실행을 요청해 구분이 안 됨)
    draft = samples.draft()
    samples.tool_record(draft, ToolName.ELECTRICAL).status = ToolStatus.FAILED
    review = samples.review(additional_tools_required=[ToolName.ELECTRICAL])

    adjusted, dropped = VerificationAgent._drop_completed_tool_requests(review, draft)

    assert adjusted.additional_tools_required == [ToolName.ELECTRICAL]
    assert dropped == []


def test_낮춘_지적과_뺀_재요청은_trace에_남는다(samples, stub_model, records):
    review = samples.review(issues=[_issue("missing_evidence", ["f1"])],
                            additional_tools_required=[ToolName.ELECTRICAL])
    trace = []

    VerificationAgent(stub_model(review)).run(samples.draft(), trace=trace)

    actions = [event.action for event in trace]
    assert "uncertain_issues_demoted" in actions
    assert "completed_tool_requests_dropped" in actions
