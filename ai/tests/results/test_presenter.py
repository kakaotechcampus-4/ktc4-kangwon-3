"""공개 진단서 변환: 진단 결과 → 요약·분야 카드·할 일·안내를 경우별로 확인한다. 결과 상태 규칙은 test_status."""

from app.results import ResultPresenter
from app.results.presenter import DISCLAIMER
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import (
    Determination, ExecutionEndReason, FinalVerificationStatus, LegalSource, RiskLevel, ToolName, ToolStatus,
)
from app.tools.customs.search import HsCase
from app.tools.customs.tool import _case_source

_PRESENTER = ResultPresenter()


def _card(dto, tool):
    return next(review for review in dto.tool_reviews if review.tool_name == tool.name)


def _scope_notice(notices):
    return [notice for notice in notices if notice.startswith("이 서비스는 통관")]


# ---- 요약·안내

def test_certification_summary_names_fields(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CHILDREN, [finding(ToolName.CHILDREN, Determination.POSSIBLY_REQUIRED)]),
        tool_result(ToolName.RADIO, [finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
    )

    dto = _PRESENTER.assessment(result)

    assert (dto.status, dto.result_status) == ("completed", "DIRECT_IMPORT_CERTIFICATION_REQUIRED")
    assert dto.summary.startswith("전파·어린이제품 분야")
    assert not _scope_notice(dto.notices)


def test_no_requirement_summary_names_checked_fields_and_scope(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        tool_result(ToolName.ELECTRICAL, [finding(ToolName.ELECTRICAL, Determination.NOT_APPLICABLE, RiskLevel.LOW)]),
    )

    dto = _PRESENTER.assessment(result)

    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    # 말투로 흐리지 않고("찾지 못했습니다(확정 아님)") 결과가 기대는 조건과 확인하지 않은 범위를 따로 적음
    assert dto.summary == ("입력하신 상품 정보 기준으로는 통관·전기용품에서 판매 전에 갖출 인증이나 허가가 없습니다. "
                           "이 서비스가 확인하지 않는 법령은 따로 확인이 필요합니다.")
    assert _scope_notice(dto.notices)


def test_no_selected_tool_has_scope_notice_without_repeating_summary():
    dto = _PRESENTER.assessment(build_dummy_assessment("prod-1").model_copy(update={
        "selected_tools": [], "tool_results": [], "findings": [], "missing_information": [],
    }))

    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    assert dto.summary == ("입력하신 상품 정보 기준으로는 인증이나 허가가 필요한 분야에 해당하지 않습니다. "
                           "이 서비스가 확인하지 않는 법령은 따로 확인이 필요합니다.")
    assert dto.notices == [*_scope_notice(dto.notices), DISCLAIMER]
    assert all(review.status == "SKIPPED" for review in dto.tool_reviews)


def test_label_ad_finding_is_mentioned_when_allowed(assessment, tool_result, finding):
    # 표시·광고는 결과 상태에서 빠지지만, 같은 화면에 "판매 가능" 요약만 보이지 않게 한 문장 덧붙임
    result = assessment(
        tool_result(ToolName.LABEL_AD, [finding(ToolName.LABEL_AD, Determination.POSSIBLY_REQUIRED, RiskLevel.HIGH)],
                    actions=["[표시·광고] 효능 표현 삭제"]),
    )

    dto = _PRESENTER.assessment(result)

    assert dto.result_status == "PURCHASING_AGENT_ALLOWED"
    assert dto.summary.endswith("다만 표시·광고 문구는 확인이 필요합니다.")
    assert _card(dto, ToolName.LABEL_AD).findings
    assert dto.required_actions == ["[표시·광고] 효능 표현 삭제"]


def test_out_of_scope_summary_and_notice(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        product_flags={"chemical_product": True},
    )

    dto = _PRESENTER.assessment(result)

    assert dto.result_status == "RECHECK_REQUIRED"
    assert dto.summary.startswith("이 상품은 생활화학제품일 수 있어")
    assert any("화학제품안전법" in notice for notice in dto.notices)
    assert not _scope_notice(dto.notices)


def test_out_of_scope_notice_stays_with_certification(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.POSSIBLY_REQUIRED)]),
        product_flags={"weapon_like": True},
    )

    dto = _PRESENTER.assessment(result)

    assert dto.result_status == "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    assert any("총포·도검" in notice for notice in dto.notices)


def test_incomplete_has_reason_notice_and_keeps_findings(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.RADIO, [finding(ToolName.RADIO, Determination.REQUIRED, RiskLevel.HIGH)]),
        verification_status=FinalVerificationStatus.INCOMPLETE,
        termination_reason=ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
    )

    dto = _PRESENTER.assessment(result)

    assert (dto.status, dto.result_status) == ("incomplete", "RECHECK_REQUIRED")
    assert dto.notices[0].startswith("추가 확인이 필요한 정보가 남아")
    assert _card(dto, ToolName.RADIO).findings


def test_notices_include_missing_information_and_disclaimer_last(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.RADIO, [finding(ToolName.RADIO, Determination.REQUIRED)]),
        missing_information=["사용 주파수", "사용 주파수"],
    )

    assert _PRESENTER.assessment(result).notices == ["사용 주파수", DISCLAIMER]


# ---- 분야 카드

def test_always_sends_six_cards_in_field_order():
    dto = _PRESENTER.assessment(build_dummy_assessment("prod-1"))

    assert [review.tool_name for review in dto.tool_reviews] == [tool.name for tool in ToolName]
    assert _card(dto, ToolName.FOOD_DRUG).status == "SKIPPED"
    assert _card(dto, ToolName.FOOD_DRUG).message


def test_failed_tool_card_hides_error(assessment, tool_result, finding):
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        tool_result(ToolName.RADIO, status=ToolStatus.FAILED).model_copy(update={"error": "TimeoutError: law.go.kr"}),
    )

    card = _card(_PRESENTER.assessment(result), ToolName.RADIO)

    assert card.status == "INCOMPLETE"
    assert "law.go.kr" not in card.message


def test_selected_tool_without_record_is_incomplete_card(assessment, tool_result, finding):
    # 선택됐는데 실행 기록이 빠지면 요약(검토 미완료)과 카드가 같은 말을 해야 한다
    result = assessment(
        tool_result(ToolName.CUSTOMS, [finding(ToolName.CUSTOMS, Determination.NOT_REQUIRED, RiskLevel.LOW)]),
        selected_tools=[ToolName.CUSTOMS, ToolName.RADIO],
    )

    dto = _PRESENTER.assessment(result)

    assert _card(dto, ToolName.RADIO).status == "INCOMPLETE"
    assert dto.summary.startswith("전파 분야 검토를 마치지 못해")


def test_partial_tool_card_is_incomplete(assessment, tool_result):
    result = assessment(tool_result(ToolName.CHILDREN, status=ToolStatus.PARTIAL))

    assert _card(_PRESENTER.assessment(result), ToolName.CHILDREN).status == "INCOMPLETE"


# ---- 할 일·칸 처리

def test_actions_follow_field_order_without_duplicates(assessment, tool_result):
    result = assessment(
        tool_result(ToolName.CHILDREN, actions=["[완구] 사입: 안전확인 신고", "공통 할 일"]),
        tool_result(ToolName.RADIO, actions=["[무선] 사입: 적합인증", "[무선] 구매대행: 인증 생략 불가", "공통 할 일"]),
        required_actions=["종합 할 일"],
    )

    assert _PRESENTER.assessment(result).required_actions == [
        "[무선] 사입: 적합인증", "[무선] 구매대행: 인증 생략 불가", "공통 할 일", "[완구] 사입: 안전확인 신고", "종합 할 일",
    ]


def test_long_fields_are_clipped_to_be_limits(assessment, tool_result, finding):
    source = LegalSource(source_name="가" * 300, law_name="나" * 300, article="다" * 300, effective_date="라" * 60)
    item = finding(ToolName.ELECTRICAL, Determination.REQUIRED, subject="마" * 300, legal_sources=[source])

    dto_finding = _card(_PRESENTER.assessment(assessment(tool_result(ToolName.ELECTRICAL, [item]))),
                        ToolName.ELECTRICAL).findings[0]
    dto_source = dto_finding.legal_sources[0]

    assert len(dto_finding.subject) == 255
    assert len(dto_source.source_name) == len(dto_source.law_name) == len(dto_source.article) == 255
    assert len(dto_source.effective_date) == 50


def test_blank_summary_and_source_name_fall_back(assessment, tool_result, finding):
    item = finding(ToolName.RADIO, Determination.REQUIRED, summary=" ", rationale="",
                   legal_sources=[LegalSource(source_name=" ")])

    dto_finding = _card(_PRESENTER.assessment(assessment(tool_result(ToolName.RADIO, [item]))),
                        ToolName.RADIO).findings[0]

    assert dto_finding.summary == item.subject
    assert dto_finding.rationale == item.subject
    assert dto_finding.legal_sources == []


def test_blank_optional_source_fields_become_none(assessment, tool_result, finding):
    source = LegalSource(source_name="전파법", law_name=" ", article="", effective_date="  ")
    item = finding(ToolName.RADIO, Determination.REQUIRED, legal_sources=[source])

    dto_source = _card(_PRESENTER.assessment(assessment(tool_result(ToolName.RADIO, [item]))),
                       ToolName.RADIO).findings[0].legal_sources[0]

    assert (dto_source.law_name, dto_source.article, dto_source.effective_date) == (None, None, None)


# ---- 통관 결정사례별 근거 (#709)

_FAN_LINES = (
    "본 상품과 같이 휴대용 및 탁상용으로 사용 가능한 4엽 플라스틱제 충전 선풍기로, 기능과 재질이 일치함.",
    "손잡이 접이식으로 휴대 및 탁상용으로 사용 가능하며, 플라스틱 재질의 충전 선풍기로 기능과 재질이 유사함.",
    "탁상용 및 휴대용으로 사용 가능하며, 플라스틱제 충전 선풍기로 기능과 재질이 일치함.",
)


def _case_sources(*hs_codes):
    """통관 Tool이 붙이는 결정사례 출처 그대로 (Tool 쪽 형식이 바뀌면 여기서 드러남)."""
    return [_case_source(HsCase(case_id=f"00720190{index:05d}", hs_codes=codes, product_name="Other fans",
                                description="", decision_reason="선풍기"))
            for index, codes in enumerate(hs_codes)]


def _customs_rationale(assessment, tool_result, item):
    return _card(_PRESENTER.assessment(assessment(tool_result(ToolName.CUSTOMS, [item]))),
                 ToolName.CUSTOMS).findings[0].rationale


def test_customs_case_lines_become_first_line_and_case_summary(assessment, tool_result, finding):
    sources = _case_sources(("8414599000",), ("8414599000",), ("8414599000", "8516799000"))
    item = finding(ToolName.CUSTOMS, Determination.POSSIBLY_REQUIRED, rationale="\n".join(_FAN_LINES),
                   legal_sources=[LegalSource(source_name="관세법", law_name="관세법", article="제226조"), *sources])

    assert _customs_rationale(assessment, tool_result, item) == (
        f"판단: {_FAN_LINES[0]}\n참고 사례: 3건 · HS 8414.59-9000, 8516.79-9000 · 아래 '근거'에서 확인")


def test_customs_single_case_rationale_is_kept(assessment, tool_result, finding):
    item = finding(ToolName.CUSTOMS, Determination.POSSIBLY_REQUIRED, rationale=_FAN_LINES[0],
                   legal_sources=_case_sources(("8414599000",)))

    assert _customs_rationale(assessment, tool_result, item) == _FAN_LINES[0]


def test_customs_rationale_is_kept_when_lines_and_cases_differ(assessment, tool_result, finding):
    item = finding(ToolName.CUSTOMS, Determination.POSSIBLY_REQUIRED, rationale="\n".join(_FAN_LINES),
                   legal_sources=_case_sources(("8414599000",), ("8414599000",)))

    assert _customs_rationale(assessment, tool_result, item) == "\n".join(_FAN_LINES)


def test_other_tool_multiline_rationale_is_kept(assessment, tool_result, finding):
    rationale = "해당할 수 있는 범위:\n제1호 미백\n제2호 주름 개선"
    item = finding(ToolName.FOOD_DRUG, Determination.POSSIBLY_REQUIRED, rationale=rationale,
                   legal_sources=_case_sources(("8414599000",), ("8414599000",)))

    rationale_out = _card(_PRESENTER.assessment(assessment(tool_result(ToolName.FOOD_DRUG, [item]))),
                          ToolName.FOOD_DRUG).findings[0].rationale
    assert rationale_out == rationale
