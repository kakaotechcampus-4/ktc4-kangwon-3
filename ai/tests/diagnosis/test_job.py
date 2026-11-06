"""실제 진단 함수를 모델·외부 호출 없이 검증한다. 파이프라인은 단계를 차례로 부르는 가짜로 바꿈."""

import re
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.tools.customs import CustomsToolError
from app.agents.verification import VerificationError
from app.clients.errors import ClientError
from app.config.session import MAX_PARALLEL_TOOLS
from app.diagnosis import job as job_module
from app.observability.logs import current_run_fields, run_log_context
from app.observability.trace import trace_note, trace_run, trace_step
from app.diagnosis.assembly import PipelineParts
from app.diagnosis.job import _alias_ids, _reporting_tools, _ToolExecution, build_job
from app.diagnosis.replay import ReplayStopped, StageReplay
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.domain.errors import AIResponseCode, AIServiceError
from app.dummy.cases import CASES, DummyCaseName
from app.pipeline.tool_executor import ToolExecutor
from app.schemas.agent import ExtractionInput, ToolSelectionItem, ToolSelectionResponse
from app.schemas.callback import PublicQuestionDto
from app.schemas.pipeline import RetryRequest, SelectionResult
from app.schemas.product import Product
from app.schemas.schemas import (
    DraftAssessment, ExecutionEndReason, FinalVerificationStatus, FollowUpQuestion, ToolName, ToolResult, ToolStatus,
    VerificationIssue, VerificationResult, VerificationStatus,
)
from app.schemas.session import DiagnosisInput, SessionAnswer
from app.sessions.job import JobDone, JobFailed, JobNeedsInput

CONTEXT = ExecutionContext(run_id="run-1", product_id="p-1", run_type=RunType.TEST)
SOURCE = ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"])


def _result(reason: ExecutionEndReason = ExecutionEndReason.COMPLETED):
    return CASES[DummyCaseName.KC_FAN].build("p-1").model_copy(update={"termination_reason": reason})


class _Progress:
    def __init__(self):
        self.stages = []
        self.tools = []

    def stage(self, stage):
        self.stages.append(stage)

    def tool(self, tool_name, status):
        self.tools.append((tool_name, status))


class _Step:
    """부른 순서를 calls에 남기는 가짜 단계."""

    def __init__(self, calls, name, returns=None, error=None):
        self.calls, self.name, self.returns, self.error = calls, name, returns, error

    def __call__(self, *args):
        self.calls.append((self.name, args))
        if self.error is not None:
            raise self.error
        return self.returns if self.returns is not None else self.name


def _parts(calls, *, extraction_error=None, verification_error=None) -> PipelineParts:
    extraction = type("Extraction", (), {"run": staticmethod(_Step(calls, "extract", returns=Product(product_id="p-1"), error=extraction_error))})()
    return PipelineParts(
        extraction=extraction,
        selector=type("Selector", (), {"run": staticmethod(_Step(calls, "select"))})(),
        tools={},
        aggregator=type("Aggregator", (), {"aggregate": staticmethod(_Step(calls, "aggregate"))})(),
        verifier=type("Verifier", (), {"run": staticmethod(_Step(calls, "verify", error=verification_error))})(),
    )


@pytest.fixture
def pipeline(monkeypatch):
    """CompliancePipeline·ToolExecutor를 가짜로. 단계를 첫 실행 + 재실행 1회 순서로 부르고 정해 둔 결과를 돌려줌."""
    state = {"result": _result(), "executor_tools": None, "executor_options": None, "verifications": []}

    class _Executor:
        def __init__(self, tools, **options):
            state["executor_tools"] = tools
            state["executor_options"] = options

        def execute_initial(self, product, selection):
            return SimpleNamespace(tool_results=[])

        def execute_retry(self, product, previous, request):
            return "retried"

    class _Pipeline:
        def __init__(self, extractor, selector, tool_executor, aggregator, verifier):
            self.stages = (extractor, selector, tool_executor, aggregator, verifier)

        def run(self, source):
            extractor, selector, executor, aggregator, verifier = self.stages
            product = extractor.run(source)
            selected = executor.execute_initial(product, selector.run(product))
            state["verifications"].append(verifier.run(aggregator.aggregate(product, selected)))
            retried = executor.execute_retry(product, selected, SimpleNamespace(retry_round=1))
            state["verifications"].append(verifier.run(aggregator.aggregate(product, retried)))
            return state["result"]

    monkeypatch.setattr(job_module, "ToolExecutor", _Executor)
    monkeypatch.setattr(job_module, "CompliancePipeline", _Pipeline)
    return state


def _no_questions(result, question_round):
    raise AssertionError("질문을 만들면 안 됨")


def test_단계마다_진행_알림을_보내고_재실행_회차도_다시_알린다(pipeline):
    progress = _Progress()

    outcome = build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert isinstance(outcome, JobDone)
    S = PipelineStage
    assert progress.stages == [
        S.EXTRACTION, S.SELECTION, S.TOOL_EXECUTION, S.AGGREGATION, S.VERIFICATION,
        S.TOOL_EXECUTION, S.AGGREGATION, S.VERIFICATION, S.FINALIZATION,
    ]


def test_추출은_원래_입력이_아니라_실행_입력_전체로_부른다(pipeline):
    calls = []
    job_input = DiagnosisInput(source=SOURCE, previous=_result(), answers=[
        SessionAnswer(question_round=1, question_key="r1_q1", answer_text="네")])

    build_job(_parts(calls), _no_questions)(job_input, CONTEXT, _Progress())

    assert calls[0] == ("extract", (job_input,))


def test_재진단은_추출_결과에_이번_회차_답변을_붙여_선택_단계로_넘긴다(pipeline):
    calls = []
    parts = _parts(calls)
    parts.extraction.run = staticmethod(lambda job_input: Product(product_id="p-1", listing_text=["무선 선풍기"]))
    previous = _result().model_copy(update={"follow_up_questions": [
        FollowUpQuestion(question="배터리로만 동작하나요?", reason="판단에 필요")]})
    job_input = DiagnosisInput(source=SOURCE, previous=previous, answers=[
        SessionAnswer(question_round=1, question_key="r1_q1", answer_text="네")])

    build_job(parts, _no_questions)(job_input, CONTEXT, _Progress())

    selected_product = next(args[0] for name, args in calls if name == "select")
    assert selected_product.listing_text == ["무선 선풍기", "[사용자 답변] 배터리로만 동작하나요? → 네"]


def _missing(result, missing: dict[ToolName, list[str]]):
    """Tool 결과에 부족한 정보(Tool이 만든 질문 문장)를 넣은 결과."""
    return result.model_copy(update={"tool_results": [
        tool_result.model_copy(update={"missing_information": missing.get(tool_result.tool_name, [])})
        for tool_result in result.tool_results
    ]})


def _questions(result, question_round):
    return [PublicQuestionDto(question_key=f"r{question_round}_q{order}", question_order=order,
                              question_text=question.question, help_text=question.reason)
            for order, question in enumerate(result.follow_up_questions, start=1)]


def test_Tool의_부족한_정보가_남으면_질문으로_넘겨_답변을_기다린다(pipeline):
    pipeline["result"] = _missing(_result(), {
        ToolName.ELECTRICAL: ["정격 전압 정보가 필요합니다."],
        ToolName.RADIO: ["정격 전압 정보가 필요합니다.", "무선 기능 정보가 필요합니다."],
    })

    outcome = build_job(_parts([]), _questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert isinstance(outcome, JobNeedsInput)
    assert outcome.result.verification_status is FinalVerificationStatus.INCOMPLETE
    # 같은 문장은 질문 하나로, 관련 Tool을 모음
    assert [(q.question, q.related_tools, q.reason) for q in outcome.result.follow_up_questions] == [
        ("정격 전압 정보가 필요합니다.", [ToolName.RADIO, ToolName.ELECTRICAL], "전파, 전기용품 판단에 필요한 정보예요."),
        ("무선 기능 정보가 필요합니다.", [ToolName.RADIO], "전파 판단에 필요한 정보예요."),
    ]
    assert [q.question_key for q in outcome.questions] == ["r1_q1", "r1_q2"]


def test_검증이_낸_질문과_같은_문장은_다시_넣지_않는다(pipeline):
    asked = FollowUpQuestion(question="정격 전압 정보가 필요합니다.", reason="검증 질문")
    pipeline["result"] = _missing(_result(ExecutionEndReason.USER_INPUT_REQUIRED), {
        ToolName.ELECTRICAL: ["정격 전압 정보가 필요합니다."]}).model_copy(update={
            "follow_up_questions": [asked], "verification_status": FinalVerificationStatus.INCOMPLETE})

    outcome = build_job(_parts([]), _questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert [q.reason for q in outcome.result.follow_up_questions] == ["검증 질문"]


def test_지난_회차에_물은_질문은_다시_묻지_않고_그대로_끝낸다(pipeline):
    pipeline["result"] = _missing(_result(), {ToolName.ELECTRICAL: ["정격 전압 정보가 필요합니다."]})
    previous = _result().model_copy(update={"follow_up_questions": [
        FollowUpQuestion(question="정격 전압 정보가 필요합니다.", reason="전기용품 판단에 필요한 정보예요.")]})
    job_input = DiagnosisInput(source=SOURCE, previous=previous, answers=[
        SessionAnswer(question_round=1, question_key="r1_q1", answer_text="잘 모르겠어요")])

    outcome = build_job(_parts([]), _no_questions)(job_input, CONTEXT, _Progress())

    assert isinstance(outcome, JobDone)
    assert outcome.result.termination_reason is ExecutionEndReason.COMPLETED


def test_두_회차_전에_물은_질문도_상품_정보의_답변_줄로_찾아_다시_묻지_않는다(pipeline):
    # 3회차: 1회차 질문(전압)은 직전 결과의 질문 칸엔 없고 상품 정보의 답변 줄에만 남음
    pipeline["result"] = _missing(_result(), {ToolName.ELECTRICAL: ["정격 전압 정보가 필요합니다."]})
    second = _result()
    previous = second.model_copy(update={
        "product": second.product.model_copy(update={"listing_text": [
            *second.product.listing_text, "[사용자 답변] 정격 전압 정보가 필요합니다. → 잘 모르겠어요"]}),
        "follow_up_questions": [FollowUpQuestion(question="무선 기능 정보가 필요합니다.", reason="전파 판단에 필요한 정보예요.")],
    })
    job_input = DiagnosisInput(source=SOURCE, previous=previous, answers=[
        SessionAnswer(question_round=2, question_key="r2_q1", answer_text="없어요")])

    outcome = build_job(_parts([]), _no_questions)(job_input, CONTEXT, _Progress())

    assert isinstance(outcome, JobDone)
    assert outcome.result.termination_reason is ExecutionEndReason.COMPLETED


def test_Tool_실행기는_조립한_Tool을_진행_알림으로_감싸_실행마다_만든다(pipeline):
    tool = _FakeTool(ToolName.RADIO)
    parts = _parts([])
    parts.tools[ToolName.RADIO] = tool

    build_job(parts, _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    wrapped = pipeline["executor_tools"][ToolName.RADIO]
    assert (wrapped._tool, wrapped.tool_name) == (tool, ToolName.RADIO)


def test_단계가_정한_실패는_코드와_재시도_여부를_그대로_실패로_돌려준다(pipeline):
    error = AIServiceError(response_code=AIResponseCode.UNSUPPORTED_SITE.value, retryable=True)
    progress = _Progress()

    outcome = build_job(_parts([], extraction_error=error), _no_questions)(
        DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert outcome == JobFailed("AI_UNSUPPORTED_SITE", retryable=True)
    assert PipelineStage.FINALIZATION not in progress.stages


def test_규칙_결과_없는_검증_실패는_재시도_가능한_파이프라인_오류로_돌려준다(pipeline):
    progress = _Progress()

    outcome = build_job(_parts([], verification_error=VerificationError("checked_finding_ids에 중복이 있습니다.")),
                        _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert outcome == JobFailed("AI_PIPELINE_ERROR", retryable=True)
    assert PipelineStage.FINALIZATION not in progress.stages


def test_검증_모델이_실패해도_규칙_결과가_통과면_재확인_필요로_진행한다(pipeline, caplog):
    rules = VerificationResult(status=VerificationStatus.APPROVED, checked_finding_ids=[])
    error = VerificationError("검토 범위가 입력과 다릅니다.", partial_result=rules)

    outcome = build_job(_parts([], verification_error=error), _no_questions)(
        DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert isinstance(outcome, JobDone)
    assert [v.status for v in pipeline["verifications"]] == [VerificationStatus.REVISION_REQUIRED] * 2
    assert pipeline["verifications"][0].review_summary == "검증 모델 검토를 마치지 못해 규칙 검사 결과만 반영함"
    # 원래 규칙 결과는 그대로
    assert rules.status is VerificationStatus.APPROVED
    assert any(r.message.startswith("검증 모델 검토 실패, 규칙 검사 결과로 진행 (status=revision_required)")
               for r in caplog.records)


def test_검증_모델이_실패해도_규칙이_정한_Tool_재실행은_그대로_둔다(pipeline):
    rules = VerificationResult(status=VerificationStatus.TOOLS_REQUIRED,
                               additional_tools_required=[ToolName.RADIO])
    error = VerificationError("검토 범위가 입력과 다릅니다.", partial_result=rules)

    build_job(_parts([], verification_error=error), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert pipeline["verifications"][0] is rules


def test_검증_모델이_실패해_규칙_결과로_진행해도_Tool의_부족한_정보는_질문으로_넘긴다(pipeline):
    rules = VerificationResult(status=VerificationStatus.APPROVED, checked_finding_ids=[])
    error = VerificationError("검토 범위가 입력과 다릅니다.", partial_result=rules)
    pipeline["result"] = _missing(_result(), {ToolName.ELECTRICAL: ["정격 전압 정보가 필요합니다."]})

    outcome = build_job(_parts([], verification_error=error), _questions)(
        DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert [v.status for v in pipeline["verifications"]] == [VerificationStatus.REVISION_REQUIRED] * 2
    assert isinstance(outcome, JobNeedsInput)
    assert outcome.result.verification_status is FinalVerificationStatus.INCOMPLETE
    assert [q.question for q in outcome.result.follow_up_questions] == ["정격 전압 정보가 필요합니다."]


def test_단계_실패는_원인을_경고로_남긴다(pipeline, caplog):
    error = VerificationError("checked_finding_ids에 중복이 있습니다.")

    build_job(_parts([], verification_error=error), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    record = next(r for r in caplog.records if r.message.startswith("진단 단계 실패"))
    assert record.levelname == "WARNING"
    # 진단서·상품·실행 ID는 실행 정보로 줄 끝에 붙어 메시지에는 넣지 않음
    assert "product_id" not in record.message
    assert "code=AI_PIPELINE_ERROR, retryable=True" in record.message
    assert record.message.endswith(": VerificationError: checked_finding_ids에 중복이 있습니다.")
    assert record.exc_info is None


def test_재실행_회차부터는_로그_줄에_회차가_붙는다(pipeline):
    seen = []
    parts = replace(_parts([]), verifier=SimpleNamespace(run=lambda draft: seen.append(dict(current_run_fields()))))

    with run_log_context(CONTEXT):
        build_job(parts, _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert [fields.get("retry_round") for fields in seen] == [None, "1"]


def test_예상_밖_예외는_그대로_올려_세션이_파이프라인_오류로_기록하게_한다(pipeline):
    with pytest.raises(RuntimeError):
        build_job(_parts([], extraction_error=RuntimeError("버그")), _no_questions)(
            DiagnosisInput(source=SOURCE), CONTEXT, _Progress())


@pytest.mark.parametrize(("answers", "expected_round"), [
    ([], 1),
    ([SessionAnswer(question_round=1, question_key="r1_q1", answer_text="네")], 2),
])
def test_답변이_필요한_결과는_다음_회차_질문과_함께_멈춘다(pipeline, answers, expected_round):
    pipeline["result"] = _result(ExecutionEndReason.USER_INPUT_REQUIRED)
    asked = []
    question = PublicQuestionDto(question_key="r1_q1", question_order=1, question_text="배터리로만 동작하나요?")

    def questions(result, question_round):
        asked.append((result, question_round))
        return [question]

    outcome = build_job(_parts([]), questions)(DiagnosisInput(source=SOURCE, answers=answers), CONTEXT, _Progress())

    assert isinstance(outcome, JobNeedsInput)
    assert outcome.questions == [question]
    assert asked == [(pipeline["result"], expected_round)]


class _FakeTool:
    """정해 둔 결과를 돌려주는 가짜 Tool. failing이면 예외."""

    def __init__(self, tool_name, failing=False):
        self.tool_name = tool_name
        self.failing = failing

    def execute(self, product, decision):
        if self.failing:
            raise RuntimeError("조회 실패")
        return ToolResult(tool_name=self.tool_name, status=ToolStatus.SUCCESS, selected=True,
                          selection_reason=decision.reason)


def _executor(progress, failing=frozenset()):
    tools = {name: _FakeTool(name, failing=name in failing) for name in ToolName}
    return _ToolExecution(ToolExecutor(_reporting_tools(tools, progress)), progress)


def _selection(selected):
    return ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=name, selected=name in selected, reason="이유") for name in ToolName])


def test_첫_실행은_선택한_Tool마다_시작·완료를_보내고_나머지는_건너뜀을_보낸다():
    progress = _Progress()

    _executor(progress).execute_initial(Product(product_id="p-1"), _selection({ToolName.RADIO}))

    assert progress.tools[:2] == [(ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]
    assert sorted(progress.tools[2:]) == sorted((name, "skipped") for name in ToolName if name is not ToolName.RADIO)


def test_Tool이_예외를_내도_완료를_보내고_결과는_실패로_남는다():
    progress = _Progress()

    result = _executor(progress, failing={ToolName.RADIO}).execute_initial(
        Product(product_id="p-1"), _selection({ToolName.RADIO}))

    assert progress.tools[:2] == [(ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]
    radio = next(r for r in result.tool_results if r.tool_name is ToolName.RADIO)
    assert radio.status is ToolStatus.FAILED


class _RaisingTool:
    def __init__(self, tool_name, error):
        self.tool_name = tool_name
        self.error = error

    def execute(self, product, decision):
        raise self.error


@pytest.mark.parametrize(("error", "level", "traceback"), [
    (ClientError("응답 없음 https://apis.data.go.kr/x?serviceKey=SECRET&page=1"), "WARNING", False),
    (RuntimeError("버그"), "ERROR", True),
])
def test_Tool_실패는_원인을_남기고_예상한_오류는_위치_없이_코드_오류는_위치까지_남긴다(caplog, error, level, traceback):
    tools = {name: _RaisingTool(name, error) for name in ToolName}
    execution = _ToolExecution(ToolExecutor(_reporting_tools(tools, _Progress())), _Progress())

    execution.execute_initial(Product(product_id="p-1"), _selection({ToolName.RADIO}))

    [record] = [r for r in caplog.records if r.name == "app.diagnosis.job"]
    assert record.levelname == level
    assert record.getMessage().startswith(f"Tool 실행 실패 {ToolName.RADIO}: {type(error).__name__}: ")
    assert "SECRET" not in record.getMessage()
    assert (record.exc_info is not None) is traceback



def test_Tool_실패_로그에_감싼_원인까지_남긴다(caplog):
    # 통관 Tool은 요건 조회의 모든 예외를 "세관장확인 요건 조회에 실패했습니다"로 감싼다.
    # 바깥 문장만 남으면 서버에서 실제 원인(시간 초과·연결 실패 등)을 알 수 없다.
    try:
        try:
            raise ClientError("연결 실패 https://apis.data.go.kr/x?serviceKey=SECRET")
        except ClientError as cause:
            raise CustomsToolError("세관장확인 요건 조회에 실패했습니다.") from cause
    except CustomsToolError as wrapped:
        error = wrapped
    tools = {name: _RaisingTool(name, error) for name in ToolName}
    execution = _ToolExecution(ToolExecutor(_reporting_tools(tools, _Progress())), _Progress())

    execution.execute_initial(Product(product_id="p-1"), _selection({ToolName.CUSTOMS}))

    [record] = [r for r in caplog.records if r.name == "app.diagnosis.job"]
    message = record.getMessage()
    assert message.startswith(f"Tool 실행 실패 {ToolName.CUSTOMS}: CustomsToolError: 세관장확인 요건 조회에 실패했습니다.")
    assert "← ClientError: 연결 실패" in message
    assert "SECRET" not in message

def test_재실행_회차는_다시_실행하는_Tool만_시작·완료를_보내고_건너뜀은_다시_보내지_않는다():
    progress = _Progress()
    execution = _executor(progress)
    product = Product(product_id="p-1")
    first = execution.execute_initial(product, _selection({ToolName.RADIO}))
    progress.tools.clear()
    verification = VerificationResult(status=VerificationStatus.TOOLS_REQUIRED,
                                      additional_tools_required=[ToolName.CUSTOMS])
    request = RetryRequest(retry_round=1, requested_tools=[ToolName.CUSTOMS], verification=verification,
                           latest_tool_results=first.tool_results)

    execution.execute_retry(product, first, request)

    assert progress.tools == [(ToolName.CUSTOMS, "started"), (ToolName.CUSTOMS, "completed")]


def test_기록_중이_아니면_Tool을_병렬_상한까지_동시에_실행한다(pipeline):
    build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert pipeline["executor_options"] == {"max_parallel": MAX_PARALLEL_TOOLS}


def test_기록_중이면_Tool을_순차로_실행한다(pipeline, tmp_path):
    with trace_run(tmp_path):
        build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert pipeline["executor_options"] == {"max_parallel": 1}


class _TracingTool:
    """실제 Tool처럼 실행 안에서 tool 단계를 여는 가짜. 실행이 겹치게 잠깐 멈춤."""

    def __init__(self, tool_name):
        self.tool_name = tool_name

    def execute(self, product, decision):
        with trace_step("tool", tool=self.tool_name):
            time.sleep(0.02)
        return ToolResult(tool_name=self.tool_name, status=ToolStatus.SUCCESS, selected=True,
                          selection_reason=decision.reason)


def test_기록_중에는_Tool_단계가_서로_안에_들어가지_않고_나란히_남는다(monkeypatch, tmp_path):
    selected = {ToolName.CUSTOMS, ToolName.ELECTRICAL, ToolName.RADIO}

    class _Pipeline:
        def __init__(self, extractor, selector, tool_executor, aggregator, verifier):
            self.stages = (extractor, selector, tool_executor)

        def run(self, source):
            extractor, selector, executor = self.stages
            product = extractor.run(source)
            executor.execute_initial(product, selector.run(product))
            return _result()

    monkeypatch.setattr(job_module, "CompliancePipeline", _Pipeline)
    parts = replace(_parts([]), tools={name: _TracingTool(name) for name in ToolName},
                    selector=type("Selector", (), {"run": staticmethod(lambda product: _selection(selected))})())

    with trace_run(tmp_path) as recorder:
        build_job(parts, _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    [tool_execution] = [step for step in recorder.steps if step["kind"] == "tool_execution"]
    tools = tool_execution["steps"]
    assert sorted(step["tool"] for step in tools) == sorted(name.value for name in selected)
    assert all(step["kind"] == "tool" and "steps" not in step for step in tools)


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def test_기록_중이면_Tool_실행_ID를_실행_안_번호로_바꿔_저장한다(tmp_path):
    with trace_run(tmp_path):
        _executor(_Progress()).execute_initial(Product(product_id="p-1"), _selection({ToolName.RADIO}))

    text = (tmp_path / "run-1.json").read_text(encoding="utf-8")
    assert UUID.search(text) is None
    assert '"execution_id": "e1"' in text


def test_진단서·검증_지적·재질문_ID도_실행_안_번호로_바꾸고_같은_ID는_같은_번호다(tmp_path):
    assessment_id, first_issue, second_issue = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333"
    question_id = "44444444-4444-4444-8444-444444444444"
    question = FollowUpQuestion.model_construct(question_id=question_id)
    draft = DraftAssessment.model_construct(assessment_id=assessment_id, follow_up_questions=[question])
    verification = VerificationResult.model_construct(issues=[
        VerificationIssue.model_construct(issue_id=first_issue), VerificationIssue.model_construct(issue_id=second_issue)],
        follow_up_questions=[question])

    with trace_run(tmp_path):
        with trace_step("verification"):
            _alias_ids(draft)
            _alias_ids(verification)
            _alias_ids(draft)
            trace_note("output", [assessment_id, first_issue, second_issue, question_id])

    text = (tmp_path / "run-1.json").read_text(encoding="utf-8")
    assert UUID.search(text) is None
    assert all(f'"{alias}"' in text for alias in ("a1", "i1", "i2", "q1"))
    assert '"a2"' not in text and '"q2"' not in text


def test_기록_중이_아니면_ID를_그대로_둔다():
    draft = DraftAssessment.model_construct(assessment_id="11111111-1111-4111-8111-111111111111")

    _alias_ids(draft)

    assert draft.assessment_id == "11111111-1111-4111-8111-111111111111"


def test_기록_중이면_단계마다_trace_단계를_열고_나온_값과_재실행_회차를_남긴다(pipeline, tmp_path):
    job_input = DiagnosisInput(source=SOURCE)

    with trace_run(tmp_path) as recorder:
        build_job(_parts([]), _no_questions)(job_input, CONTEXT, _Progress())

    assert [(step["kind"], step.get("round")) for step in recorder.steps] == [
        ("extraction", None), ("selection", None), ("tool_execution", 0), ("aggregation", 0), ("verification", 0),
        ("tool_execution", 1), ("aggregation", 1), ("verification", 1),
    ]
    extraction, selection = recorder.steps[:2]
    assert extraction["input"] == job_input.model_dump(mode="json")
    assert extraction["output"]["product_id"] == "p-1"
    assert (selection["output"], recorder.steps[5]["output"], recorder.steps[-1]["output"]) == (
        "select", "retried", "verify")


def test_검증_단계가_실패하면_검증_trace_단계에_원인을_남긴다(pipeline, tmp_path):
    with trace_run(tmp_path) as recorder:
        build_job(_parts([], verification_error=VerificationError("검토 ID 중복")), _no_questions)(
            DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    verification = recorder.steps[-1]
    assert verification["kind"] == "verification"
    assert verification["error"]["type"] == "VerificationError"
    assert "output" not in verification
    assert recorder.finish["reason"] == "failed"
    assert (recorder.finish["stage"], recorder.finish["code"], recorder.finish["retryable"]) == (
        "verification", AIResponseCode.PIPELINE_ERROR.value.code, True)
    assert recorder.finish["error"]["cause"]["type"] == "VerificationError"
    assert recorder.finish["at"]["step"] == verification["id"]


def test_끝까지_돈_실행은_종료_이유와_최종_결과를_결말로_남긴다(pipeline, tmp_path):
    with trace_run(tmp_path) as recorder:
        build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert recorder.finish == {"reason": "completed", "result": pipeline["result"].model_dump(mode="json")}


def test_질문하고_멈춘_실행은_질문_회차와_질문을_결말로_남긴다(pipeline, tmp_path):
    pipeline["result"] = _result(ExecutionEndReason.USER_INPUT_REQUIRED)
    question = PublicQuestionDto(question_key="r1_q1", question_order=1, question_text="배터리로만 동작하나요?")

    with trace_run(tmp_path) as recorder:
        build_job(_parts([]), lambda result, question_round: [question])(
            DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert recorder.finish["reason"] == "user_input_required"
    assert recorder.finish["question_round"] == 1
    assert recorder.finish["questions"] == [question.model_dump(mode="json")]


def _saved_trace():
    """첫 회차 추출·선택·Tool 실행 결과가 남은 이전 trace."""
    selection = ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=tool, selected=False, reason="해당 없음") for tool in ToolName])
    return {"steps": [
        {"kind": "extraction", "output": Product(product_id="p-1", listing_text=["저장한 추출"]).model_dump(mode="json")},
        {"kind": "selection", "output": selection.model_dump(mode="json")},
        {"kind": "tool_execution", "round": 0, "output": SelectionResult(
            selection=selection, tool_results=[], tool_result_history=[]).model_dump(mode="json")},
    ]}


def test_다시_실행은_시작_단계_앞은_저장한_결과를_쓰고_재실행_회차는_실제로_돈다(pipeline, tmp_path):
    calls = []
    replay = StageReplay.from_trace(_saved_trace(), "aggregation")

    with trace_run(tmp_path) as recorder:
        build_job(_parts(calls), _no_questions, replay)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert [name for name, _ in calls] == ["aggregate", "verify", "aggregate", "verify"]
    assert [step.get("replayed", False) for step in recorder.steps] == [True, True, True] + [False] * 5
    assert recorder.steps[0]["output"]["listing_text"] == ["저장한 추출"]
    # 저장한 Tool 실행 결과를 집계에 넘김
    assert isinstance(calls[0][1][1], SelectionResult)


def test_하나만_다시_실행하면_시작_단계를_마치고_멈춘다(pipeline, tmp_path):
    calls = []
    replay = StageReplay.from_trace(_saved_trace(), "selection", only=True)

    with trace_run(tmp_path) as recorder:
        with pytest.raises(ReplayStopped):
            build_job(_parts(calls), _no_questions, replay)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert [name for name, _ in calls] == ["select"]
    assert [step["kind"] for step in recorder.steps] == ["extraction", "selection"]
    assert recorder.finish == {"reason": "stopped", "stage": "selection"}
