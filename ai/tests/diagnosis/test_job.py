"""실제 진단 함수를 모델·외부 호출 없이 검증한다. 파이프라인은 단계를 차례로 부르는 가짜로 바꿈."""

import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.agents.verification import VerificationError
from app.config.session import MAX_PARALLEL_TOOLS
from app.diagnosis import job as job_module
from app.observability.logs import current_run_fields, run_log_context
from app.observability.trace import trace_run, trace_step
from app.diagnosis.assembly import PipelineParts
from app.diagnosis.job import build_job
from app.diagnosis.replay import ReplayStopped, StageReplay
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.domain.errors import AIResponseCode, AIServiceError
from app.dummy.cases import CASES, DummyCaseName
from app.schemas.agent import ExtractionInput, ToolSelectionItem, ToolSelectionResponse
from app.schemas.callback import PublicQuestionDto
from app.schemas.pipeline import SelectionResult
from app.schemas.product import Product
from app.schemas.schemas import ExecutionEndReason, FollowUpQuestion, ToolName, ToolResult, ToolStatus
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
    state = {"result": _result(), "executor_tools": None, "executor_options": None}

    class _Executor:
        def __init__(self, tools, **options):
            state["executor_tools"] = tools
            state["executor_options"] = options

        def execute_initial(self, product, selection):
            return SimpleNamespace(tool_results=[])

        def execute_retry(self, product, previous, request):
            return "retried"

    class _Pipeline:
        def __init__(self, extractor, selector, tool_executor, aggregator, verifier, stage_hook):
            self.stages = (extractor, selector, tool_executor, aggregator, verifier)
            self.hook = stage_hook

        def run(self, source):
            extractor, selector, executor, aggregator, verifier = self.stages
            hook = self.hook
            product = hook("extraction", 0, lambda: extractor.run(source))
            selection = hook("selection", 0, lambda: selector.run(product))
            selected = hook("tool_execution", 0, lambda: executor.execute_initial(product, selection))
            draft = hook("aggregation", 0, lambda: aggregator.aggregate(product, selected))
            hook("verification", 0, lambda: verifier.run(draft))
            retried = hook("tool_execution", 1,
                           lambda: executor.execute_retry(product, selected, SimpleNamespace(retry_round=1)))
            draft = hook("aggregation", 1, lambda: aggregator.aggregate(product, retried))
            hook("verification", 1, lambda: verifier.run(draft))
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


def test_Tool_실행기는_조립한_Tool과_진행_알림·실패_로그_hook으로_실행마다_만든다(pipeline, caplog):
    parts = _parts([])
    parts.tools[ToolName.RADIO] = _FakeTool(ToolName.RADIO)
    progress = _Progress()

    build_job(parts, _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert pipeline["executor_tools"] is parts.tools
    hook = pipeline["executor_options"]["tool_hook"]
    failing = _FakeTool(ToolName.RADIO, failing=True)
    with pytest.raises(RuntimeError):
        hook(ToolName.RADIO, lambda: failing.execute(None, None))
    assert progress.tools == [(ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith("Tool 실행 실패")] == [
        f"Tool 실행 실패 {ToolName.RADIO}: RuntimeError: 조회 실패"]


def test_단계가_정한_실패는_코드와_재시도_여부를_그대로_실패로_돌려준다(pipeline):
    error = AIServiceError(response_code=AIResponseCode.UNSUPPORTED_SITE.value, retryable=True)
    progress = _Progress()

    outcome = build_job(_parts([], extraction_error=error), _no_questions)(
        DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert outcome == JobFailed("AI_UNSUPPORTED_SITE", retryable=True)
    assert PipelineStage.FINALIZATION not in progress.stages


def test_검증_실패는_재시도_가능한_파이프라인_오류로_돌려준다(pipeline):
    progress = _Progress()

    outcome = build_job(_parts([], verification_error=VerificationError("checked_finding_ids에 중복이 있습니다.")),
                        _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, progress)

    assert outcome == JobFailed("AI_PIPELINE_ERROR", retryable=True)
    assert PipelineStage.FINALIZATION not in progress.stages


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


def _selection(selected):
    return ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=name, selected=name in selected, reason="이유") for name in ToolName])


def test_기록_중이_아니면_Tool을_병렬_상한까지_동시에_실행한다(pipeline):
    build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert pipeline["executor_options"]["max_parallel"] == MAX_PARALLEL_TOOLS


def test_기록_중이면_Tool을_순차로_실행한다(pipeline, tmp_path):
    with trace_run(tmp_path):
        build_job(_parts([]), _no_questions)(DiagnosisInput(source=SOURCE), CONTEXT, _Progress())

    assert pipeline["executor_options"]["max_parallel"] == 1


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
        def __init__(self, extractor, selector, tool_executor, aggregator, verifier, stage_hook):
            self.stages = (extractor, selector, tool_executor)
            self.hook = stage_hook

        def run(self, source):
            extractor, selector, executor = self.stages
            product = self.hook("extraction", 0, lambda: extractor.run(source))
            selection = self.hook("selection", 0, lambda: selector.run(product))
            self.hook("tool_execution", 0, lambda: executor.execute_initial(product, selection))
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
    # 단계 trace가 닫힌 뒤 멈춤 → 시작 단계는 실패 없이 output까지
    assert recorder.steps[-1]["output"] == "select"
    assert "error" not in recorder.steps[-1]
    assert recorder.finish == {"reason": "stopped", "stage": "selection"}
