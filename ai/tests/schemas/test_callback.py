"""콜백 이벤트·공개 진단서 스키마의 camelCase 경계와 검증 규칙을 확인한다 (#310)."""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.callback import (
    ProductAwaitingInputEvent, ProductFailedEvent, ProductProgressEvent, ProductResultEvent, PublicAssessmentDto,
    PublicErrorDto, PublicPipelineStage, PublicProductEvent, PublicQuestionDto, PublicToolReviewDto,
)
from app.schemas.schemas import ToolName

_BASE = {"event_id": "e-1", "diagnosis_id": "d-1", "product_id": "p-1", "run_id": "run-1", "sequence": 1}


def _assessment(**fields) -> PublicAssessmentDto:
    values = {"status": "completed", "result_status": "DIRECT_IMPORT_CERTIFICATION_REQUIRED", "summary": "요약"}
    return PublicAssessmentDto(**{**values, **fields})


def _question(key: str = "battery_only", order: int = 1) -> PublicQuestionDto:
    return PublicQuestionDto(question_key=key, question_order=order, question_text="내장 배터리로만 동작하나요?")


def test_이벤트는_camelCase로_나가고_eventType이_붙는다():
    event = ProductProgressEvent(**_BASE, stage=PublicPipelineStage.TOOL_EXECUTION, stage_status="started",
                                 tool_name=ToolName.ELECTRICAL)

    assert event.model_dump(mode="json", by_alias=True) == {
        "eventId": "e-1", "diagnosisId": "d-1", "productId": "p-1", "runId": "run-1", "sequence": 1,
        "eventType": "product_progress", "stage": "tool_execution", "stageStatus": "started",
        "toolName": "electrical_safety",
    }


@pytest.mark.parametrize("event", [
    ProductProgressEvent(**_BASE, stage=PublicPipelineStage.EXTRACTION, stage_status="started"),
    ProductAwaitingInputEvent(**_BASE, question_round=1, questions=[_question()]),
    ProductResultEvent(**_BASE, assessment=_assessment()),
    ProductFailedEvent(**_BASE, error=PublicErrorDto(code="AI-TIMEOUT", message="시간 초과", retryable=True)),
])
def test_eventType으로_4종을_구분해_읽는다(event):
    adapter = TypeAdapter(PublicProductEvent)

    payload = event.model_dump(mode="json", by_alias=True)

    assert adapter.validate_python(payload) == event


def test_toolName은_Tool_실행_단계에서만_받는다():
    with pytest.raises(ValidationError, match="Tool 실행 단계"):
        ProductProgressEvent(**_BASE, stage=PublicPipelineStage.SELECTION, stage_status="started",
                             tool_name=ToolName.ELECTRICAL)


@pytest.mark.parametrize("sequence", [0, "1"])
def test_sequence는_1부터_정수만(sequence):
    with pytest.raises(ValidationError):
        ProductProgressEvent(**{**_BASE, "sequence": sequence}, stage=PublicPipelineStage.EXTRACTION,
                             stage_status="started")


@pytest.mark.parametrize("questions", [
    [_question("battery_only", 1), _question("battery_only", 2)],
    [_question("battery_only", 1), _question("target_age", 1)],
])
def test_질문_키와_순서는_중복될_수_없다(questions):
    with pytest.raises(ValidationError, match="중복"):
        ProductAwaitingInputEvent(**_BASE, question_round=1, questions=questions)


@pytest.mark.parametrize("question_round", [0, 3])
def test_질문은_2회차까지(question_round):
    with pytest.raises(ValidationError):
        ProductAwaitingInputEvent(**_BASE, question_round=question_round, questions=[_question()])


def test_질문_키는_BE_칸_길이_50자까지():
    with pytest.raises(ValidationError):
        _question(key="k" * 51)


def test_미완료_결과는_안내가_필요하고_재확인_필요로만_낸다():
    with pytest.raises(ValidationError, match="공개 안내"):
        _assessment(status="incomplete", result_status="RECHECK_REQUIRED")
    with pytest.raises(ValidationError, match="재확인 필요"):
        _assessment(status="incomplete", result_status="PURCHASING_AGENT_ALLOWED", notices=["안내"])

    assert _assessment(status="incomplete", result_status="RECHECK_REQUIRED", notices=["안내"]).notices == ["안내"]


def test_같은_분야_카드는_한_번만():
    review = PublicToolReviewDto(agent_type="ELECTRICAL", status="COMPLETED")

    with pytest.raises(ValidationError, match="중복"):
        _assessment(tool_reviews=[review, review])


def test_분야_카드_상태는_BE_값만():
    with pytest.raises(ValidationError):
        PublicToolReviewDto(agent_type="ELECTRICAL", status="reviewed")


def test_정의하지_않은_필드는_받지_않는다():
    with pytest.raises(ValidationError):
        ProductResultEvent(**_BASE, assessment=_assessment(), status="finished")
