"""VerificationAgent 동작 검증. 실제 ML API 호출 없이 모델을 스텁으로 대체한다."""

import pytest
import json

from app.agents.verification import (
    VerificationAgent,
    VerificationError,
    _Issue,
    _Question,
    _Review,
)
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination,
    DraftAssessment,
    ElectricalAssessment,
    FollowUpQuestion,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
    TraceEvent,
    VerificationStatus, 
)


def _finding() -> RegulatoryFinding:
    # possibly_required는 확정적 판단이 아니므로 실자료 근거 규칙의 대상이 아니다.
    return RegulatoryFinding(
        finding_id="f1",
        tool_name=ToolName.ELECTRICAL,
        subject="전지 내장 기기",
        determination=Determination.POSSIBLY_REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        summary="추가 확인이 필요합니다.",
        rationale="전지 용량 표기가 확인되지 않았습니다.",
    )


def _draft(product: Product | None = None) -> DraftAssessment:
    """규칙 검사를 통과하는 최소 초안. 6개 툴 기록을 모두 채운다."""
    finding = _finding()
    records = [
        ToolResult(
            tool_name=name,
            status=ToolStatus.NOT_APPLICABLE,
            selected=False,
            selection_reason="선택 단계에서 대상이 아니라고 판단했습니다.",
        )
        for name in ToolName
        if name != ToolName.ELECTRICAL
    ]
    records.append(
        ToolResult(
            tool_name=ToolName.ELECTRICAL,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="전기로 작동합니다.",
            result=ElectricalAssessment(safety_management_required=True),
            findings=[finding],
        )
    )
    return DraftAssessment(
        product=product or Product(product_id="p1"),
        selected_tools=[ToolName.ELECTRICAL],
        tool_results=records,
        findings=[finding],
        overall_status=OverallStatus.ACTION_REQUIRED,
        summary="전기안전 항목의 추가 확인이 필요합니다.",
    )


def _review(**overrides) -> _Review:
    """strict 모드라 모든 필드가 required이므로 기본값을 여기서 채운다."""
    values = {
        "issues": [],
        "additional_tools_required": [],
        "follow_up_questions": [],
        "checked_finding_ids": ["f1"],
    }
    values.update(overrides)
    return _Review(**values)


class _StubModel:
    """with_structured_output(...).invoke(...) 인터페이스만 흉내 낸 테스트 전용 스텁."""

    def __init__(self, review: _Review) -> None:
        self._review = review
        self.structured_kwargs: dict | None = None
        self.received_messages: list | None = None
        self.received_config: dict | None = None

    def with_structured_output(self, schema: type, **kwargs):
        assert schema is _Review
        self.structured_kwargs = kwargs
        return self

    def invoke(self, messages: list, config: dict | None = None) -> _Review:
        self.received_messages = messages
        self.received_config = config
        return self._review


class _RaisingModel:
    def with_structured_output(self, schema: type, **kwargs):
        return self

    def invoke(self, messages: list, config: dict | None = None) -> _Review:
        raise RuntimeError("rate limit exceeded")


@pytest.fixture(autouse=True)
def _disable_usage_file_writes(monkeypatch):
    """에이전트 단위 테스트가 로컬 usage 로그를 만들지 않게 한다."""
    monkeypatch.setattr("app.agents.verification.record", lambda *args, **kwargs: None)


# ---------- 규칙 검사 (API 없이) ----------


def test_규칙_검사는_모델_없이도_동작한다():
    result = VerificationAgent().verify_rules(_draft())

    assert result.status is VerificationStatus.APPROVED
    assert result.issues == []
    # 의미 검토를 하지 않았으므로 검토한 판단 ID를 채우지 않는다.
    assert result.checked_finding_ids == []


def test_상품에_무선_신호가_있는데_전파_툴이_없으면_지적한다():
    draft = _draft(Product(product_id="p1", wireless_comm=True))

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.REVISION_REQUIRED
    assert ToolName.RADIO in result.additional_tools_required
    issue = next(issue for issue in result.issues if issue.issue_type.value == "missing_tool")
    assert issue.severity == "warning"


def test_미선택_툴에_실행_결과가_있으면_모순으로_지적한다():
    draft = _draft()
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


def test_확정적_판단에_실자료_근거가_없으면_지적한다():
    draft = _draft()
    # legal_sources가 비어 있는 상태로 확정 판단만 바꾼다.
    draft.findings[0].determination = Determination.REQUIRED
    draft.tool_results[-1].findings[0].determination = Determination.REQUIRED

    result = VerificationAgent().verify_rules(draft)

    assert result.status is VerificationStatus.REVISION_REQUIRED
    assert any("실자료" in issue.description for issue in result.issues)


def test_모델_없이_verify를_부르면_규칙_결과를_보존하고_실패한다():
    with pytest.raises(VerificationError) as exc_info:
        VerificationAgent().verify(_draft())

    assert exc_info.value.partial_result is not None
    assert exc_info.value.partial_result.review_summary.startswith("규칙 검사만")


# ---------- 모델 검토 ----------


def test_strict_json_schema로_구조화_출력을_요구한다():
    stub = _StubModel(_review())

    VerificationAgent(model=stub)

    assert stub.structured_kwargs == {"method": "json_schema", "strict": True}


def test_문제가_없으면_approved를_돌려준다():
    agent = VerificationAgent(model=_StubModel(_review()))

    result = agent.verify(_draft())

    assert result.status is VerificationStatus.APPROVED
    assert result.checked_finding_ids == ["f1"]


def test_모델_지적과_규칙_지적이_함께_병합된다():
    review = _review(
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
    # 규칙 쪽에서도 critical 지적이 나오는 초안을 쓴다.
    draft = _draft(Product(product_id="p1", wireless_comm=True))

    result = VerificationAgent(model=_StubModel(review)).verify(draft)

    assert len(result.issues) == 2
    # 규칙이 찾은 critical은 모델이 지울 수 없다.
    assert result.status is VerificationStatus.REVISION_REQUIRED


def test_trace에_DraftAssessment부터_VerificationResult까지_변환을_남긴다():
    trace: list[TraceEvent] = []

    result = VerificationAgent(model=_StubModel(_review())).verify(_draft(), trace=trace)

    assert result.status is VerificationStatus.APPROVED
    assert [event.sequence for event in trace] == list(range(1, len(trace) + 1))
    assert [event.action for event in trace] == [
        "verification_started",
        "rules_started",
        "rules_completed",
        "model_review_started",
        "model_review_completed",
        "scope_validated",
        "result_merged",
        "verification_completed",
    ]
    assert "DraftAssessment" in trace[0].detail
    assert "_Review" in trace[4].detail
    assert "VerificationResult" in trace[-1].detail


def test_추가_툴_요청이_있으면_코드가_revision_required로_정한다():
    review = _review(additional_tools_required=[ToolName.RADIO])

    result = VerificationAgent(model=_StubModel(review)).verify(_draft())

    assert result.status is VerificationStatus.REVISION_REQUIRED
    assert "추가 검토 도구: radio_compliance" in result.review_summary


def test_필수_질문이_있으면_user_input_required가_된다():
    review = _review(
        follow_up_questions=[
            _Question(
                question="전지 용량(Wh)이 표기되어 있습니까?",
                reason="안전확인 대상 판단에 필요합니다.",
                related_tools=[ToolName.ELECTRICAL],
                required=True,
            )
        ]
    )

    result = VerificationAgent(model=_StubModel(review)).verify(_draft())

    assert result.status is VerificationStatus.USER_INPUT_REQUIRED

def test_겹치는_질문은_required가_강한_쪽을_남긴다():
    draft = _draft()
    existing = FollowUpQuestion(
        question="전지 용량(Wh)이 표기되어 있습니까?",
        reason="초안 단계에서 확인하지 못했습니다.",
        related_tools=[ToolName.ELECTRICAL],
        required=False,
    )
    draft.follow_up_questions = [existing]
    review = _review(
        follow_up_questions=[
            _Question(
                question="전지 용량(Wh)이 표기되어 있습니까?",
                reason="안전확인 대상 판단에 필요합니다.",
                related_tools=[ToolName.ELECTRICAL],
                required=True,
            )
        ]
    )

    result = VerificationAgent(model=_StubModel(review)).verify(draft)

    assert len(result.follow_up_questions) == 1
    merged = result.follow_up_questions[0]
    assert merged.required is True
    assert merged.question_id == existing.question_id  # 기존 식별자 보존
    assert result.status is VerificationStatus.USER_INPUT_REQUIRED

def test_모델_호출에_사용량_콜백을_전달하고_성공을_기록한다(monkeypatch):
    stub = _StubModel(_review())
    captured: dict = {}
    usage = object()

    monkeypatch.setattr("app.agents.verification.from_handler", lambda handler: usage)

    def capture(agent, call_usage, **kwargs):
        captured.update(agent=agent, usage=call_usage, **kwargs)

    monkeypatch.setattr("app.agents.verification.record", capture)

    VerificationAgent(
        model=stub,
        configured_model="openai/gpt-4.1-mini",
    ).verify(_draft())

    assert len(stub.received_config["callbacks"]) == 1
    assert captured["agent"] == "verification"
    assert captured["usage"] is usage
    assert captured["configured_model"] == "openai/gpt-4.1-mini"
    assert captured["subject_id"] == "p1"
    assert captured["elapsed_ms"] >= 0
    assert "ok" not in captured  # 성공은 record()의 기본값을 쓴다.


def test_모델_호출_실패도_오류_타입과_함께_기록한다(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr("app.agents.verification.from_handler", lambda handler: None)

    def capture(agent, call_usage, **kwargs):
        captured.update(agent=agent, usage=call_usage, **kwargs)

    monkeypatch.setattr("app.agents.verification.record", capture)

    with pytest.raises(VerificationError):
        VerificationAgent(model=_RaisingModel()).verify(_draft())

    assert captured["agent"] == "verification"
    assert captured["usage"] is None
    assert captured["ok"] is False
    assert captured["error_type"] == "RuntimeError"
    assert captured["elapsed_ms"] >= 0


# ---------- 실패 처리 ----------


def test_검토_범위가_다르면_실패_trace와_규칙_결과를_남긴다():
    agent = VerificationAgent(model=_StubModel(_review(checked_finding_ids=[])))
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError, match="검토 범위") as exc_info:
        agent.verify(_draft(), trace=trace)

    assert trace[-1].action == "review_validation_failed"
    assert trace[-1].status == "failed"
    assert exc_info.value.partial_result is not None
    assert exc_info.value.partial_result.checked_finding_ids == []


def test_검토_범위에_중복이_있으면_실패한다():
    agent = VerificationAgent(model=_StubModel(_review(checked_finding_ids=["f1", "f1"])))

    with pytest.raises(VerificationError, match="중복"):
        agent.verify(_draft())


def test_존재하지_않는_판단_ID를_참조하면_실패한다():
    review = _review(
        issues=[
            _Issue(
                severity="warning",
                issue_type="contradiction",
                description="없는 판단을 가리킨다.",
                related_finding_ids=["없는-id"],
                recommended_action=None,
            )
        ]
    )
    agent = VerificationAgent(model=_StubModel(review))

    with pytest.raises(VerificationError, match="존재하지 않는"):
        agent.verify(_draft())


def test_모델_호출_실패는_원인을_보존한_채_감싸진다():
    agent = VerificationAgent(model=_RaisingModel())

    with pytest.raises(VerificationError) as exc_info:
        agent.verify(_draft())

    # 원인이 삼켜지지 않아야 traceback으로 근본 원인을 찾을 수 있다.
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "rate limit exceeded" in str(exc_info.value.__cause__)
    assert exc_info.value.partial_result is not None


# ---------- 모델 입력 ----------


def test_조회_파라미터와_원시_응답은_모델에_보내지_않는다():
    draft = _draft()
    draft.tool_results[-1].query = {"api_key": "절대-보내면-안-됨"}
    draft.tool_results[-1].raw_response = {"body": "원시 응답"}
    stub = _StubModel(_review())

    VerificationAgent(model=stub).verify(draft)

    payload = stub.received_messages[-1]["content"]
    assert "절대-보내면-안-됨" not in payload
    assert "원시 응답" not in payload

def test_툴_판단은_최상위_findings로만_모델에_보낸다():
    stub = _StubModel(_review())

    VerificationAgent(model=stub).verify(_draft())

    payload = json.loads(stub.received_messages[-1]["content"])["draft"]
    assert [f["finding_id"] for f in payload["findings"]] == ["f1"]
    assert all("findings" not in record for record in payload["tool_results"])

def test_출력_스키마를_프롬프트에_중복으로_붙이지_않는다():
    # with_structured_output이 스키마를 API에 직접 전달하므로 프롬프트에는 넣지 않는다.
    stub = _StubModel(_review())

    VerificationAgent(model=stub).verify(_draft())

    system_prompt = stub.received_messages[0]["content"]
    assert "checked_finding_ids" in system_prompt  # 규칙 설명은 있다
    assert "앞 단계의 도메인 판단을 반복하지 않는다" in system_prompt
    assert "다시 `missing_evidence`로 지적하지 않는다" in system_prompt
    assert "$defs" not in system_prompt  # JSON Schema 본문은 없다
