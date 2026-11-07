"""진단 trace: 단계 trace hook·ID 번호 바꾸기, 이미지 자르기 결과. 기록 중이 아니면 원래와 같다."""

import io
import re

import pytest
from PIL import Image

from app.diagnosis.tracing import TracedImageSplitter, TraceStageHook, alias_ids
from app.observability.trace import trace_note, trace_run, trace_step
from app.pipeline.image_split import ImageSplitter
from app.pipeline.tool_executor import ToolExecutor
from app.schemas.agent import ExtractionInput, ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import (
    DraftAssessment, FollowUpQuestion, ToolName, ToolResult, ToolStatus, VerificationIssue, VerificationResult,
)
from app.schemas.session import DiagnosisInput

TALL_URL = "https://img.example/tall.png"
SHORT_URL = "https://img.example/short.png"
BROKEN_URL = "https://img.example/broken.png"


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


PAGES = {TALL_URL: _png(100, 400), SHORT_URL: _png(100, 100), BROKEN_URL: b"not an image"}


def test_기록_중이_아니면_원래_이미지_자르기와_결과가_같다():
    urls = [SHORT_URL, TALL_URL]

    assert TracedImageSplitter(fetch=PAGES.__getitem__).prepare(urls) == ImageSplitter(
        fetch=PAGES.__getitem__).prepare(urls)


def test_기록_중이면_이미지마다_자름·안_자름·상한_초과와_보낸_장수를_남긴다(tmp_path):
    # 100x400은 조각 5개, 상한 6이면 두 번째 긴 이미지는 넘김
    splitter = TracedImageSplitter(fetch=PAGES.__getitem__, max_tiles=6)

    with trace_run(tmp_path) as recorder:
        prepared = splitter.prepare([SHORT_URL, TALL_URL, BROKEN_URL, TALL_URL])

    assert recorder.info["image_split"] == {
        "images": [
            {"url": SHORT_URL, "result": "not_split"},
            {"url": TALL_URL, "result": "split", "tiles": 5},
            {"url": BROKEN_URL, "result": "not_split"},
            {"url": TALL_URL, "result": "over_limit", "tiles": 5},
        ],
        "sent": len(prepared),
    }
    assert len(prepared) == 8


def test_data_URI_이미지는_본문_대신_형식만_남긴다(tmp_path):
    with trace_run(tmp_path) as recorder:
        TracedImageSplitter(fetch=PAGES.__getitem__).prepare(["data:image/png;base64,AAAA"])

    assert recorder.info["image_split"]["images"] == [{"url": "data:image/png;base64,…(생략)", "result": "not_split"}]


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
JOB_INPUT = DiagnosisInput(source=ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"]))


def test_trace_hook은_단계마다_trace_단계를_열고_output을_남기며_추출엔_입력도_남긴다(tmp_path):
    hook = TraceStageHook(JOB_INPUT)

    with trace_run(tmp_path) as recorder:
        hook("extraction", 0, lambda: Product(product_id="p-1"))
        hook("selection", 0, lambda: "선택")
        hook("aggregation", 0, lambda: "종합")
        hook("verification", 2, lambda: "검증")

    # 앞 두 단계는 재실행 회차가 없어 round를 안 남김
    assert [(step["kind"], step.get("round")) for step in recorder.steps] == [
        ("extraction", None), ("selection", None), ("aggregation", 0), ("verification", 2)]
    assert recorder.steps[0]["input"] == JOB_INPUT.model_dump(mode="json")
    assert [("input" in step) for step in recorder.steps] == [True, False, False, False]
    assert [step["output"] for step in recorder.steps[1:]] == ["선택", "종합", "검증"]


def test_trace_hook은_단계가_실패하면_output_없이_원인을_남기고_그대로_올린다(tmp_path):
    def fail():
        raise ValueError("검증 실패")

    with trace_run(tmp_path) as recorder:
        with pytest.raises(ValueError):
            TraceStageHook(JOB_INPUT)("verification", 0, fail)

    [step] = recorder.steps
    assert step["error"]["type"] == "ValueError"
    assert "output" not in step


def test_기록_중이_아니면_trace_hook은_결과만_돌려준다():
    assert TraceStageHook(JOB_INPUT)("selection", 0, lambda: "선택") == "선택"


def test_trace_hook은_Tool_실행_ID를_실행_안_번호로_바꿔_저장한다(tmp_path):
    tools = {name: _FakeTool(name) for name in ToolName}
    executor = ToolExecutor(tools)
    selection = ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=name, selected=name is ToolName.RADIO, reason="이유") for name in ToolName])

    with trace_run(tmp_path):
        TraceStageHook(JOB_INPUT)(
            "tool_execution", 0, lambda: executor.execute_initial(Product(product_id="p-1"), selection))

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
            alias_ids(draft)
            alias_ids(verification)
            alias_ids(draft)
            trace_note("output", [assessment_id, first_issue, second_issue, question_id])

    text = (tmp_path / "run-1.json").read_text(encoding="utf-8")
    assert UUID.search(text) is None
    assert all(f'"{alias}"' in text for alias in ("a1", "i1", "i2", "q1"))
    assert '"a2"' not in text and '"q2"' not in text


def test_기록_중이_아니면_ID를_그대로_둔다():
    draft = DraftAssessment.model_construct(assessment_id="11111111-1111-4111-8111-111111111111")

    alias_ids(draft)

    assert draft.assessment_id == "11111111-1111-4111-8111-111111111111"


class _FakeTool:
    def __init__(self, tool_name):
        self.tool_name = tool_name

    def execute(self, product, decision):
        return ToolResult(tool_name=self.tool_name, status=ToolStatus.SUCCESS, selected=True,
                          selection_reason=decision.reason)
