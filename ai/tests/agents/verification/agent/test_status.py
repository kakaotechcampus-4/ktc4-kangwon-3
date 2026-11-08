"""검증 상태 우선순위: Tool로 못 고치는 critical → 필수 질문 → 추가 Tool → 승인 (#64, #153, #165)."""

from app.agents.verification import VerificationAgent
from app.agents.verification.schemas import _Issue
from app.schemas.product import Product
from app.schemas.schemas import Determination, RegulatoryFinding, RiskLevel, ToolName, VerificationStatus


def test_모델_지적과_규칙_지적이_함께_병합된다(samples, stub_model, records):
    review = samples.review(
        issues=[
            _Issue(
                severity="warning",
                issue_type="missing_evidence",
                description="인용문이 결론과 직접 연결되지 않습니다.",
                related_finding_ids=["f1"],
                recommended_action="해당 조문을 다시 확인하세요.",
            )
        ],
    )
    # 규칙 검사에서 누락된 RADIO Tool 재실행 요청이 추가된다.
    draft = samples.draft(Product(product_id="p1", wireless_comm=True))

    result = VerificationAgent(stub_model(review)).run(draft)

    assert len(result.issues) == 2
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_추가_툴_요청이_있으면_tools_required로_정한다(samples, stub_model, records):
    review = samples.review(additional_tools_required=[ToolName.RADIO])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert "추가 검토 도구: radio_compliance" in result.review_summary
    assert result.status is VerificationStatus.TOOLS_REQUIRED


def test_필수_질문이_있으면_user_input_required가_된다(samples, stub_model, records):
    review = samples.review(follow_up_questions=[samples.battery_question()])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert result.status is VerificationStatus.USER_INPUT_REQUIRED


def test_추가_툴과_필수_질문이_겹치면_질문을_먼저_본다(samples, stub_model, records):
    review = samples.review(
        additional_tools_required=[ToolName.RADIO],
        follow_up_questions=[samples.battery_question()],
    )

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    # 툴 재실행만 반복하지 않도록 사람만 풀 수 있는 막힘을 먼저 드러낸다.
    assert result.status is VerificationStatus.USER_INPUT_REQUIRED
    # 툴 요청 자체는 결과에 그대로 남아 파이프라인이 함께 처리할 수 있다.
    assert ToolName.RADIO in result.additional_tools_required


def test_critical_지적은_필수_질문보다_먼저다(samples, stub_model, records):
    # 불확실 판단의 근거 부족 지적은 경고로 낮아지므로(#652) 낮아지지 않는 모순 지적으로 검사한다
    review = samples.review(
        issues=[samples.contradiction()],
        follow_up_questions=[samples.battery_question()],
    )

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    # 틀린 전제 위에서 사용자에게 묻지 않도록 초안 보완을 먼저 요구한다.
    assert result.status is VerificationStatus.REVISION_REQUIRED


def test_확정_판단의_결함이_경고로만_적히고_불확실_판단_치명만_있으면_낮춘_뒤_통과한다(samples, stub_model, records):
    # #652 낮추기는 치명 지적만 건드린다. 확정 판단(f2)의 실제 결함을 모델이 경고로 적으면 막히지 않고 통과하므로,
    # 확정 판단 결함을 막는 건 모델이 치명으로 적어 주는 데 달려 있다 (#691 리뷰에서 짚은 전제를 테스트로 남김)
    draft = samples.draft()
    definitive = RegulatoryFinding(
        finding_id="f2", tool_name=ToolName.ELECTRICAL, subject="안전확인 대상",
        determination=Determination.NOT_REQUIRED, risk_level=RiskLevel.LOW,
        summary="안전확인 대상이 아닙니다.", rationale="품목표에 없습니다.", legal_sources=[samples.law_source()],
    )
    samples.tool_record(draft, ToolName.ELECTRICAL).findings.append(definitive)
    draft.findings.append(definitive.model_copy(deep=True))
    real_defect = _Issue(severity="warning", issue_type="contradiction", description="요약이 판정과 다릅니다.",
                         related_finding_ids=["f2"], recommended_action=None)
    uncertain_only = _Issue(severity="critical", issue_type="insufficient_product_data",
                            description="전원 방식 정보가 없습니다.", related_finding_ids=["f1"], recommended_action=None)
    review = samples.review(issues=[real_defect, uncertain_only], checked_finding_ids=["f1", "f2"])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert [issue.severity for issue in result.issues] == ["warning", "warning"]
    assert result.status is VerificationStatus.APPROVED_WITH_WARNINGS


def test_critical_수정과_추가_툴이_겹치면_revision_required가_된다(samples, stub_model, records):
    # 모델이 요청한 RADIO는 미선택 Tool이라 후처리에서 빠지지 않고, 모순 지적은 경고로 낮아지지 않는다 (#652)
    review = samples.review(issues=[samples.contradiction()], additional_tools_required=[ToolName.RADIO])

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert result.status is VerificationStatus.REVISION_REQUIRED
    assert ToolName.RADIO in result.additional_tools_required
