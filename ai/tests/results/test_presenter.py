"""진단 결과 → 결과 상태·공개 진단서 변환을 경우별로 확인한다."""

from app.results import ResultPresenter, ResultStatus, decide_result_status
from app.results.presenter import DISCLAIMER
from app.results.status import DecisionReason
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import (
    Determination, ExecutionEndReason, FinalAssessment, FinalVerificationStatus, LegalSource, RegulatoryFinding,
    RiskLevel, ToolName, ToolResult, ToolStatus,
)

_PRESENTER = ResultPresenter()


def _finding(tool, determination, risk=RiskLevel.MEDIUM, **extra) -> RegulatoryFinding:
    values = dict(subject=f"{tool.name} 판단", summary="요약", rationale="근거")
    values.update(extra)
    return RegulatoryFinding(tool_name=tool, determination=determination, risk_level=risk, **values)


def _tool(tool, findings=(), status=ToolStatus.SUCCESS, actions=(), missing=()) -> ToolResult:
    return ToolResult(
        tool_name=tool, status=status, selected=True, selection_reason="선택",
        findings=list(findings), required_actions=list(actions), missing_information=list(missing),
    )


def _assessment(*tool_results: ToolResult, **changes) -> FinalAssessment:
    """더미 결과의 상품·검증만 빌려 tool 결과를 바꾼 진단 결과."""
    base = build_dummy_assessment("prod-1")
    values = dict(
        selected_tools=[item.tool_name for item in tool_results],
        tool_results=list(tool_results),
        findings=[finding for item in tool_results for finding in item.findings],
        required_actions=[],
        missing_information=[],
    )
    values.update(changes)
    return base.model_copy(update=values)


def _card(dto, tool):
    return next(review for review in dto.tool_reviews if review.tool_name == tool.name)


# ---- 결과 상태

def test_certification_required_lists_fields_in_order():
    result = _assessment(
        _tool(ToolName.CHILDREN, [_finding(ToolName.CHILDREN, Determination.POSSIBLY_REQUIRED)]),
        _tool(ToolName.RADIO, [_finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
    )

    decision = decide_result_status(result)
    dto = _PRESENTER.assessment(result)

    assert decision.status is ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED
    assert decision.tools == (ToolName.RADIO, ToolName.CHILDREN)
    assert dto.status == "completed"
    assert dto.result_status == "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    assert dto.summary.startswith("전파·어린이제품 분야")


def test_certification_wins_over_insufficient_information():
    result = _assessment(
        _tool(ToolName.ELECTRICAL, [_finding(ToolName.ELECTRICAL, Determination.POSSIBLY_REQUIRED)]),
        _tool(ToolName.CHILDREN, [_finding(ToolName.CHILDREN, Determination.INSUFFICIENT_INFORMATION, RiskLevel.UNKNOWN)]),
    )

    assert decide_result_status(result).status is ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED


def test_insufficient_information_needs_recheck():
    result = _assessment(
        _tool(ToolName.ELECTRICAL, [_finding(ToolName.ELECTRICAL, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        _tool(ToolName.CHILDREN, [_finding(ToolName.CHILDREN, Determination.INSUFFICIENT_INFORMATION)]),
    )

    decision = decide_result_status(result)

    assert decision.status is ResultStatus.RECHECK_REQUIRED
    assert decision.reason is DecisionReason.INSUFFICIENT_INFORMATION
    assert decision.tools == (ToolName.CHILDREN,)
    assert _PRESENTER.assessment(result).status == "completed"


def test_unknown_risk_needs_recheck_even_without_insufficient_determination():
    result = _assessment(_tool(ToolName.RADIO, [_finding(ToolName.RADIO, Determination.NOT_REQUIRED, RiskLevel.UNKNOWN)]))

    assert decide_result_status(result).reason is DecisionReason.INSUFFICIENT_INFORMATION


def test_low_risk_insufficient_information_does_not_block():
    result = _assessment(
        _tool(ToolName.FOOD_DRUG, [_finding(ToolName.FOOD_DRUG, Determination.INSUFFICIENT_INFORMATION, RiskLevel.LOW)]),
    )

    assert decide_result_status(result).status is ResultStatus.PURCHASING_AGENT_ALLOWED


def test_no_requirement_allows_purchasing_agent():
    result = _assessment(
        _tool(ToolName.CUSTOMS, [_finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        _tool(ToolName.ELECTRICAL, [_finding(ToolName.ELECTRICAL, Determination.NOT_APPLICABLE, RiskLevel.LOW)]),
    )

    decision = decide_result_status(result)
    dto = _PRESENTER.assessment(result)

    assert decision.reason is DecisionReason.NO_REQUIREMENT
    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    assert "확정 아님" in dto.summary


def test_failed_tool_needs_recheck_and_hides_error():
    result = _assessment(
        _tool(ToolName.CUSTOMS, [_finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        _tool(ToolName.RADIO, status=ToolStatus.FAILED).model_copy(update={"error": "TimeoutError: law.go.kr"}),
    )

    decision = decide_result_status(result)
    card = _card(_PRESENTER.assessment(result), ToolName.RADIO)

    assert decision.status is ResultStatus.RECHECK_REQUIRED
    assert decision.reason is DecisionReason.TOOL_FAILED
    assert decision.tools == (ToolName.RADIO,)
    assert card.status == "INCOMPLETE"
    assert "law.go.kr" not in card.message


def test_selected_tool_without_record_is_incomplete_card_and_recheck():
    # 선택됐는데 실행 기록이 빠지면 요약(검토 미완료)과 카드가 같은 말을 해야 한다
    result = _assessment(
        _tool(ToolName.CUSTOMS, [_finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        selected_tools=[ToolName.CUSTOMS, ToolName.RADIO],
    )

    dto = _PRESENTER.assessment(result)

    assert decide_result_status(result).reason is DecisionReason.TOOL_FAILED
    assert _card(dto, ToolName.RADIO).status == "INCOMPLETE"
    assert dto.summary.startswith("전파 분야 검토를 마치지 못해")


def test_partial_tool_card_is_incomplete():
    result = _assessment(_tool(ToolName.CHILDREN, status=ToolStatus.PARTIAL))

    assert _card(_PRESENTER.assessment(result), ToolName.CHILDREN).status == "INCOMPLETE"


def test_incomplete_assessment_is_recheck_with_reason_notice():
    result = _assessment(
        _tool(ToolName.RADIO, [_finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
        verification_status=FinalVerificationStatus.INCOMPLETE,
        termination_reason=ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
    )

    dto = _PRESENTER.assessment(result)

    assert dto.status == "incomplete"
    assert dto.result_status == "RECHECK_REQUIRED"
    assert dto.notices[0].startswith("추가 확인이 필요한 정보가 남아")
    # 미완료여도 찾은 판단은 카드로 보여 준다
    assert _card(dto, ToolName.RADIO).findings


def test_label_ad_is_excluded_from_badge():
    result = _assessment(
        _tool(ToolName.LABEL_AD, [_finding(ToolName.LABEL_AD, Determination.POSSIBLY_REQUIRED, RiskLevel.HIGH)],
              actions=["[표시·광고] 효능 표현 삭제"]),
    )

    decision = decide_result_status(result)
    dto = _PRESENTER.assessment(result)

    assert decision.reason is DecisionReason.NO_REGULATED_TOOL
    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    assert _card(dto, ToolName.LABEL_AD).findings
    assert dto.required_actions == ["[표시·광고] 효능 표현 삭제"]


def test_no_selected_tool_allows_with_notice():
    dto = _PRESENTER.assessment(_assessment())

    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    assert any("인증·허가 대상 분야를 찾지 못했습니다" in notice for notice in dto.notices)
    assert all(review.status == "SKIPPED" for review in dto.tool_reviews)


# ---- 공개 진단서 모양

def test_always_sends_six_cards_in_field_order():
    dto = _PRESENTER.assessment(build_dummy_assessment("prod-1"))

    assert [review.tool_name for review in dto.tool_reviews] == [tool.name for tool in ToolName]
    assert _card(dto, ToolName.FOOD_DRUG).status == "SKIPPED"
    assert _card(dto, ToolName.FOOD_DRUG).message


def test_actions_follow_field_order_without_duplicates():
    result = _assessment(
        _tool(ToolName.CHILDREN, actions=["[완구] 사입: 안전확인 신고", "공통 할 일"]),
        _tool(ToolName.RADIO, actions=["[무선] 사입: 적합인증", "[무선] 구매대행: 인증 생략 불가", "공통 할 일"]),
        required_actions=["종합 할 일"],
    )

    assert _PRESENTER.assessment(result).required_actions == [
        "[무선] 사입: 적합인증", "[무선] 구매대행: 인증 생략 불가", "공통 할 일", "[완구] 사입: 안전확인 신고", "종합 할 일",
    ]


def test_notices_include_missing_information_and_disclaimer_last():
    result = _assessment(_tool(ToolName.RADIO), missing_information=["사용 주파수", "사용 주파수"])

    notices = _PRESENTER.assessment(result).notices

    assert notices == ["사용 주파수", DISCLAIMER]


def test_long_fields_are_clipped_to_be_limits():
    source = LegalSource(source_name="가" * 300, law_name="나" * 300, article="다" * 300, effective_date="라" * 60)
    finding = _finding(ToolName.ELECTRICAL, Determination.REQUIRED, subject="마" * 300, legal_sources=[source])
    result = _assessment(_tool(ToolName.ELECTRICAL, [finding]))

    dto_finding = _card(_PRESENTER.assessment(result), ToolName.ELECTRICAL).findings[0]
    dto_source = dto_finding.legal_sources[0]

    assert len(dto_finding.subject) == 255
    assert len(dto_source.source_name) == len(dto_source.law_name) == len(dto_source.article) == 255
    assert len(dto_source.effective_date) == 50


def test_blank_summary_and_source_name_fall_back():
    finding = _finding(ToolName.RADIO, Determination.REQUIRED, summary=" ", rationale="",
                       legal_sources=[LegalSource(source_name=" ")])
    result = _assessment(_tool(ToolName.RADIO, [finding]))

    dto_finding = _card(_PRESENTER.assessment(result), ToolName.RADIO).findings[0]

    assert dto_finding.summary == finding.subject
    assert dto_finding.rationale == finding.subject
    assert dto_finding.legal_sources == []


def test_blank_optional_source_fields_become_none():
    source = LegalSource(source_name="전파법", law_name=" ", article="", effective_date="  ")
    result = _assessment(_tool(ToolName.RADIO, [_finding(ToolName.RADIO, Determination.REQUIRED, legal_sources=[source])]))

    dto_source = _card(_PRESENTER.assessment(result), ToolName.RADIO).findings[0].legal_sources[0]

    assert (dto_source.law_name, dto_source.article, dto_source.effective_date) == (None, None, None)
