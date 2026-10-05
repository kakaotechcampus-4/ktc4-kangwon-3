"""외부 모델 없이 6개 Tool의 구조적 동일성 및 실패 제외 계약을 검증한다."""

from datetime import timedelta

import pytest

from app.pipeline.early_stop import has_no_progress
from app.pipeline.tool_executor import ToolExecutor
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.pipeline import RetryRequest, SelectionResult
from app.schemas.product import Product
from app.schemas.schemas import (
    AdvertisingAssessment, ChildrenAssessment, CustomsAssessment, Determination,
    ElectricalAssessment, FollowUpQuestion, FoodDrugAssessment, LegalSource,
    RadioAssessment, RegulatoryFinding, RiskLevel, ToolName, ToolResult,
    ToolStatus, VerificationIssue, VerificationIssueType, VerificationResult,
    VerificationStatus,
)
from app.tools.base import RegulatoryTool


def _state(name: ToolName, round_number: int):
    assessment = {
        ToolName.CUSTOMS: CustomsAssessment,
        ToolName.RADIO: RadioAssessment,
        ToolName.FOOD_DRUG: FoodDrugAssessment,
        ToolName.ELECTRICAL: ElectricalAssessment,
        ToolName.CHILDREN: ChildrenAssessment,
        ToolName.LABEL_AD: lambda: AdvertisingAssessment(overall_risk=RiskLevel.LOW),
    }[name]()
    finding = RegulatoryFinding(
        tool_name=name, subject="적용 요건", determination=Determination.POSSIBLY_REQUIRED,
        risk_level=RiskLevel.MEDIUM, summary="추가 검토 필요", rationale="근거가 부족함",
        requirements=["요건 A", "요건 B"], product_facts_used=["상품 사실"],
        assumptions=["미확인 가정"], confidence=0.5,
        legal_sources=[LegalSource(source_name="기관", quoted_text="근거", source_url="https://example.test/law")],
    )
    result = ToolResult(
        tool_name=name, status=ToolStatus.SUCCESS, selected=True,
        selection_reason="초기 선택" if round_number == 0 else "재실행 선택",
        execution_id=f"{name}-{round_number}", retry_round=round_number,
        result=assessment, findings=[finding], required_actions=["조치"],
        missing_information=["정보"],
    )
    selection = ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=tool, selected=tool is name, reason="선택 판단")
        for tool in ToolName
    ])
    snapshot = SelectionResult(
        selection=selection, tool_results=[result],
        tool_result_history=[result.model_copy(deep=True)],
    )
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED, additional_tools_required=[name],
        checked_finding_ids=[finding.finding_id], review_summary="검증 보완 필요",
        issues=[VerificationIssue(
            severity="warning", issue_type=VerificationIssueType.MISSING_EVIDENCE,
            description="출처 보완", related_finding_ids=[finding.finding_id],
            recommended_action="근거 조회",
        )],
        follow_up_questions=[FollowUpQuestion(question="추가 정보?", reason="보완", related_tools=[name])],
    )
    return snapshot, verification


def _compare(before, before_review, after, after_review, *, tools=None, retry_round=1):
    return has_no_progress(
        before, before_review, after, after_review,
        executed_tools=tools if tools is not None else before_review.additional_tools_required,
        retry_round=retry_round,
    )


@pytest.mark.parametrize("name", list(ToolName))
def test_최초와_재실행의_ID와_시각이_달라도_내용이_같으면_개선이_없다(name):
    before, before_review = _state(name, 0)
    after, after_review = _state(name, 1)
    after.tool_results[0].executed_at += timedelta(seconds=1)
    after_review.verified_at += timedelta(seconds=1)
    assert _compare(before, before_review, after, after_review)


@pytest.mark.parametrize("field,value", [
    ("determination", Determination.REQUIRED), ("risk_level", RiskLevel.HIGH),
    ("subject", "다른 판단"), ("summary", "다른 요약"), ("rationale", "다른 설명"),
    ("requirements", ["새 요건"]), ("product_facts_used", ["새 사실"]),
    ("assumptions", []), ("confidence", 0.9),
    ("legal_sources", [LegalSource(source_name="새 기관", quoted_text="새 근거")]),
])
def test_판단이나_근거가_달라지면_중단하지_않는다(field, value):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    setattr(after.tool_results[0].findings[0], field, value)
    assert not _compare(before, review, after, next_review)


@pytest.mark.parametrize("change", ["detail", "missing", "actions", "issue", "issue_action", "question", "summary", "requested"])
def test_상세결과와_검증정보의_변화도_보존한다(change):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    if change == "detail":
        after.tool_results[0].result.frequency_bands = ["2.4 GHz"]
    elif change == "missing":
        after.tool_results[0].missing_information = []
    elif change == "actions":
        after.tool_results[0].required_actions = ["새 조치"]
    elif change == "issue":
        next_review.issues[0].description = "다른 지적"
    elif change == "issue_action":
        next_review.issues[0].recommended_action = "다른 보완"
    elif change == "question":
        next_review.follow_up_questions[0].question = "다른 질문?"
    elif change == "summary":
        next_review.review_summary = "다른 검증 요약"
    else:
        next_review.additional_tools_required = [ToolName.ELECTRICAL]
    assert not _compare(before, review, after, next_review)


def test_목록_순서는_무시하되_중복_개수는_보존한다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    after.tool_results[0].findings[0].requirements.reverse()
    assert _compare(before, review, after, next_review)
    after.tool_results[0].findings[0].requirements.append("요건 A")
    assert not _compare(before, review, after, next_review)


@pytest.mark.parametrize("side", ["previous", "current"])
def test_실패_이력은_유효상태가_PARTIAL이어도_중단하지_않는다(side):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    state = before if side == "previous" else after
    state.tool_results[0].status = ToolStatus.PARTIAL
    state.tool_result_history[0].status = ToolStatus.FAILED
    assert not _compare(before, review, after, next_review)


@pytest.mark.parametrize("problem", ["history", "round", "execution_id", "error", "detail", "findings", "duplicate_tool", "reference", "duplicate_finding"])
def test_불완전한_기록이나_불명확한_참조로_중단하지_않는다(problem):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    if problem == "history":
        after.tool_result_history = []
    elif problem == "round":
        after.tool_result_history[0].retry_round = 0
    elif problem == "execution_id":
        after.tool_result_history[0].execution_id = "다른 실행"
    elif problem == "error":
        after.tool_result_history[0].error = "실패"
    elif problem == "detail":
        after.tool_results[0].result = None
    elif problem == "findings":
        after.tool_results[0].findings = []
    elif problem == "duplicate_tool":
        after.tool_results.append(after.tool_results[0].model_copy(deep=True))
    elif problem == "reference":
        next_review.issues[0].related_finding_ids = ["존재하지 않는 판단"]
    else:
        after.tool_results[0].findings.append(after.tool_results[0].findings[0].model_copy(deep=True))
    assert not _compare(before, review, after, next_review)


@pytest.mark.parametrize("status", [status for status in VerificationStatus if status is not VerificationStatus.TOOLS_REQUIRED])
def test_다른_종료분기에는_동일결과_정책을_적용하지_않는다(status):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    next_review.status = status
    assert not _compare(before, review, after, next_review)


def test_여러_Tool_중_하나라도_실패하면_중단하지_않는다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    for state, check, round_number in ((before, review, 0), (after, next_review, 1)):
        other, _ = _state(ToolName.ELECTRICAL, round_number)
        state.tool_results.extend(other.tool_results)
        state.tool_result_history.extend(other.tool_result_history)
        check.additional_tools_required.append(ToolName.ELECTRICAL)
    assert _compare(before, review, after, next_review)
    after.tool_result_history[-1].status = ToolStatus.FAILED
    assert not _compare(before, review, after, next_review)


def test_검증의_지적대상이_다르면_ID를_제외해도_변화로_본다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    for state in (before, after):
        additional = state.tool_results[0].findings[0].model_copy(deep=True)
        additional.finding_id = "다른 판단 ID"
        additional.subject = "다른 대상"
        state.tool_results[0].findings.append(additional)
    next_review.issues[0].related_finding_ids = ["다른 판단 ID"]
    assert not _compare(before, review, after, next_review)


def test_비교는_입력객체를_변경하지_않는다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    inputs = (before, review, after, next_review)
    saved = [item.model_dump(mode="json") for item in inputs]
    assert _compare(*inputs)
    assert [item.model_dump(mode="json") for item in inputs] == saved


def test_HS_후보의_우선순위가_바뀌면_변화로_본다():
    before, review = _state(ToolName.CUSTOMS, 0)
    after, next_review = _state(ToolName.CUSTOMS, 1)
    before.tool_results[0].result.hs_code_candidates = ["1111111111", "2222222222"]
    after.tool_results[0].result.hs_code_candidates = ["1111111111", "2222222222"]
    assert _compare(before, review, after, next_review)
    after.tool_results[0].result.hs_code_candidates.reverse()
    assert not _compare(before, review, after, next_review)


def test_문자열_Tool_이름도_enum과_같은_결과로_비교한다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    assert _compare(before, review, after, next_review, tools=[ToolName.RADIO.value])


@pytest.mark.parametrize("side", ["previous", "current"])
def test_실행_ID가_없는_기록은_최신결과와_일치해도_중단하지_않는다(side):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    state = before if side == "previous" else after
    state.tool_results[0].execution_id = None
    state.tool_result_history[0].execution_id = None
    assert not _compare(before, review, after, next_review)


def test_최신_결과의_회차가_이력과_다르면_실행_ID가_같아도_중단하지_않는다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    after.tool_results[0].retry_round = 0
    # 실제 이력은 요청 회차(1)이며, 실행 ID도 최신 결과와 같다.
    assert not _compare(before, review, after, next_review)


def test_이번_회차에_재실행되지_않았다면_최신과_이력이_일치해도_중단하지_않는다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 0)
    assert not _compare(before, review, after, next_review, retry_round=1)


@pytest.mark.parametrize("previous_round", [1, 2])
def test_이전_상태의_회차가_현재_요청_이상이면_중단하지_않는다(previous_round):
    before, review = _state(ToolName.RADIO, previous_round)
    after, next_review = _state(ToolName.RADIO, 1)
    assert not _compare(before, review, after, next_review, retry_round=1)


@pytest.mark.parametrize("retry_round", [0, -1, True, "1", 1.0])
def test_유효하지_않은_재실행_회차로_중단하지_않는다(retry_round):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    assert not _compare(before, review, after, next_review, retry_round=retry_round)


@pytest.mark.parametrize("status", [status for status in VerificationStatus if status is not VerificationStatus.TOOLS_REQUIRED])
def test_이전_검증이_재실행을_요구하지_않았다면_중단하지_않는다(status):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    review.status = status
    assert not _compare(before, review, after, next_review)


@pytest.mark.parametrize("tools", [[], [ToolName.RADIO, ToolName.RADIO], [ToolName.ELECTRICAL]])
def test_실행_대상이_이전_요청과_다르면_정상_기록이_있어도_중단하지_않는다(tools):
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    for state, round_number in ((before, 0), (after, 1)):
        other, _ = _state(ToolName.ELECTRICAL, round_number)
        state.tool_results.extend(other.tool_results)
        state.tool_result_history.extend(other.tool_result_history)
    # ELECTRICAL도 정상 기록이 있지만 실제 요청은 RADIO뿐이다.
    assert _compare(before, review, after, next_review)
    assert not _compare(before, review, after, next_review, tools=tools)


def test_요청하지_않은_Tool의_판단이_바뀌어도_변화로_본다():
    before, review = _state(ToolName.RADIO, 0)
    after, next_review = _state(ToolName.RADIO, 1)
    other, _ = _state(ToolName.ELECTRICAL, 0)
    before.tool_results.extend(other.tool_results)
    after.tool_results.extend(result.model_copy(deep=True) for result in other.tool_results)
    assert _compare(before, review, after, next_review)
    after.tool_results[-1].findings[0].rationale = "새 판단 근거"
    assert not _compare(before, review, after, next_review)


class _RepeatingTool(RegulatoryTool):
    """정상 실행은 동일 내용을 반환하고 지정한 호출에서만 실패한다."""

    def __init__(self, name: ToolName, *, failed_calls: set[int] | None = None):
        self.tool_name = name
        self.calls = 0
        self.failed_calls = failed_calls or set()

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        self.calls += 1
        if self.calls in self.failed_calls:
            raise RuntimeError("일시적인 조회 실패")
        state, _ = _state(self.tool_name, 0)
        return state.tool_results[0]


def _review_for(state: SelectionResult, name: ToolName) -> VerificationResult:
    """실제 Executor가 생성한 판단 ID를 사용하는 동일한 검증 내용을 만든다."""
    _, review = _state(name, 0)
    ids = [finding.finding_id for result in state.tool_results for finding in result.findings]
    review.checked_finding_ids = ids
    review.issues[0].related_finding_ids = ids
    return review


@pytest.mark.parametrize("name", list(ToolName))
@pytest.mark.parametrize("fail_first_retry", [False, True])
def test_실제_Executor의_전체_결과와_누적이력에서_반복과_실패복구를_구분한다(name, fail_first_retry):
    tools = {
        tool: _RepeatingTool(tool, failed_calls={2} if fail_first_retry and tool == name else set())
        for tool in ToolName
    }
    executor = ToolExecutor(tools)
    product = Product(product_id="early-stop-product")
    initial, _ = _state(name, 0)
    previous = executor.execute_initial(product, initial.selection)
    previous_review = _review_for(previous, name)
    expected = [False, False, True] if fail_first_retry else [True, True, True]

    for retry_round, no_progress in enumerate(expected, start=1):
        request = RetryRequest(
            retry_round=retry_round, requested_tools=[name],
            verification=previous_review, latest_tool_results=previous.tool_results,
        )
        current = executor.execute_retry(product, previous, request)
        current_review = _review_for(current, name)
        assert len(current.tool_results) == len(ToolName)
        assert len(current.tool_result_history) == retry_round + 1
        assert all(result.status is ToolStatus.SKIPPED for result in current.tool_results if result.tool_name != name)
        assert _compare(previous, previous_review, current, current_review, retry_round=retry_round) is no_progress
        if fail_first_retry and retry_round == 1:
            latest = next(result for result in current.tool_results if result.tool_name == name)
            assert latest.status is ToolStatus.PARTIAL
            assert current.tool_result_history[-1].status is ToolStatus.FAILED
        previous, previous_review = current, current_review
