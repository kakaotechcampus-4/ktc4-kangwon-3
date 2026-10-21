"""세션 상태 변경 → 콜백 이벤트 변환을 실제 세션 저장소의 변경으로 확인한다."""

from itertools import count

from app.callbacks.events import EventBuilder
from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicAssessmentDto, PublicFindingDto, PublicQuestionDto, PublicToolReviewDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import DiagnosisSession
from app.sessions.store import SessionStore


_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


class _Presenter:
    """고정 진단서를 돌려주는 가짜 변환기."""

    def assessment(self, result):
        return PublicAssessmentDto(status="completed", result_status="DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                                   summary=result.summary)


class _BrokenPresenter(_Presenter):
    def assessment(self, result):
        raise ValueError("변환 실패")


def _inputs(*product_ids: str) -> list[ExtractionInput]:
    return [ExtractionInput(product_id=product_id, text_blocks=["상품 설명"]) for product_id in product_ids]


def _builder(presenter=None) -> EventBuilder:
    ids = count(1)
    return EventBuilder(presenter or _Presenter(), new_event_id=lambda: f"e-{next(ids)}")


def _running(product_id: str = "p-1") -> tuple[SessionStore, ExecutionContext, DiagnosisSession]:
    store = SessionStore()
    context = store.accept("d-1", _inputs(product_id))[0].context
    return store, context, store.start(context)


def _awaiting(product_id: str):
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def _summary(events) -> list[tuple]:
    return [(event.event_type, event.sequence, getattr(event, "stage", None), getattr(event, "stage_status", None))
            for event in events]


def test_단계가_바뀌면_앞_단계_완료와_새_단계_시작을_순서대로_만든다():
    store, context, started = _running()
    builder = _builder()

    events = [*builder.build(started),
              *builder.build(store.update_stage(context, PipelineStage.EXTRACTION)),
              *builder.build(store.update_stage(context, PipelineStage.SELECTION)),
              *builder.build(store.finish(context, build_dummy_assessment("p-1")))]

    assert _summary(events) == [
        ("product_progress", 1, "extraction", "started"),
        ("product_progress", 2, "extraction", "completed"),
        ("product_progress", 3, "selection", "started"),
        ("product_result", 4, None, None),
    ]
    assert [event.event_id for event in events] == ["e-1", "e-2", "e-3", "e-4"]
    assert {(event.diagnosis_id, event.product_id, event.run_id) for event in events} == {
        ("d-1", "p-1", context.run_id)}


def test_실행_시작과_내부_전용_단계와_같은_단계_반복은_이벤트를_만들지_않는다():
    store, context, started = _running()
    builder = _builder()

    assert builder.build(started) == []
    assert builder.build(store.update_stage(context, PipelineStage.PIPELINE)) == []
    assert len(builder.build(store.update_stage(context, PipelineStage.EXTRACTION))) == 1
    assert builder.build(store.update_stage(context, PipelineStage.EXTRACTION)) == []


def test_답변_대기는_세션에_기록된_회차와_질문으로_질문_이벤트를_보낸다():
    store, context, _ = _running()

    [event] = _builder().build(store.finish(context, _awaiting("p-1"), _QUESTIONS))

    assert (event.event_type, event.question_round, event.questions) == ("product_awaiting_input", 1, _QUESTIONS)


def test_실패와_시간_초과는_마지막_단계와_공개_문구로_보낸다():
    store, context, _ = _running()
    builder = _builder()
    builder.build(store.update_stage(context, PipelineStage.TOOL_EXECUTION))

    [event] = builder.build(store.fail(context, error_code="AI_TIMEOUT", retryable=True))

    assert (event.event_type, event.sequence, event.stage) == ("product_failed", 2, "tool_execution")
    assert (event.error.code, event.error.message, event.error.retryable) == (
        "AI_TIMEOUT", "진단 시간이 초과되었습니다.", True)


def test_대기_중_시간_초과는_단계_없이_실패로_보낸다():
    store = SessionStore()
    context = store.accept("d-1", _inputs("p-1"))[0].context

    [event] = _builder().build(store.fail(context, error_code="AI_TIMEOUT", retryable=True))

    assert (event.sequence, event.stage) == (1, None)


def test_모르는_오류_코드는_기본_문구로_보낸다():
    store, context, _ = _running()

    [event] = _builder().build(store.fail(context, error_code="SOMETHING_NEW", retryable=False))

    assert (event.error.code, event.error.message) == ("SOMETHING_NEW", "진단 실행 중 오류가 발생했습니다.")


def test_끝난_실행의_늦은_변경은_이벤트를_만들지_않는다():
    store, context, _ = _running()
    builder = _builder()
    finished = store.finish(context, build_dummy_assessment("p-1"))
    builder.build(finished)

    # 같은 변경이 두 번 전달돼도 결과 이벤트는 한 번
    assert builder.build(finished) == []


def test_실행마다_sequence를_1부터_따로_센다():
    builder = _builder()
    first_store, first, first_started = _running("p-1")
    second_store, second, _ = _running("p-2")

    builder.build(first_store.update_stage(first, PipelineStage.EXTRACTION))
    [other] = builder.build(second_store.update_stage(second, PipelineStage.EXTRACTION))

    assert (other.run_id, other.sequence) == (second.run_id, 1)


def test_진단서_없는_실행은_보내지_않는다():
    store = SessionStore()
    context = store.accept("d-1", _inputs("p-1"))[0].context
    session = store.start(context).model_copy(update={
        "context": context.model_copy(update={"diagnosis_id": None, "run_type": RunType.TEST}),
    })

    assert _builder().build(session) == []


def test_진단서_변환이_실패하면_실패_이벤트로_끝낸다(caplog):
    # 마지막 이벤트가 빠지면 BE에서 진행 중으로 남음
    store, context, _ = _running()
    builder = _builder(_BrokenPresenter())
    builder.build(store.update_stage(context, PipelineStage.EXTRACTION))

    [event] = builder.build(store.finish(context, build_dummy_assessment("p-1")))

    assert (event.event_type, event.sequence, event.stage) == ("product_failed", 2, "extraction")
    assert (event.error.code, event.error.retryable) == ("AI_PIPELINE_ERROR", False)
    assert "변환 실패" in caplog.text


def test_변환_실패로_끝난_실행의_늦은_변경은_이벤트를_만들지_않는다():
    store, context, _ = _running()
    builder = _builder(_BrokenPresenter())
    finished = store.finish(context, build_dummy_assessment("p-1"))
    builder.build(finished)

    # 같은 변경이 다시 와도 실패 이벤트는 한 번
    builder._presenter = _Presenter()
    assert builder.build(finished) == []


def test_Tool_진행은_단계_이벤트에_이어_번호를_매기고_공개_이름으로_보낸다():
    store, context, _ = _running()
    builder = _builder()

    events = [*builder.build(store.update_stage(context, PipelineStage.SELECTION)),
              *builder.build(tool_stage := store.update_stage(context, PipelineStage.TOOL_EXECUTION)),
              *builder.build_tool(tool_stage, ToolName.ELECTRICAL, "started"),
              *builder.build_tool(tool_stage, ToolName.ELECTRICAL, "completed"),
              *builder.build_tool(tool_stage, ToolName.RADIO, "skipped"),
              *builder.build(store.update_stage(context, PipelineStage.AGGREGATION))]

    assert [(*row, getattr(event, "tool_name", None)) for row, event in zip(_summary(events), events)] == [
        ("product_progress", 1, "selection", "started", None),
        ("product_progress", 2, "selection", "completed", None),
        ("product_progress", 3, "tool_execution", "started", None),
        ("product_progress", 4, "tool_execution", "started", "ELECTRICAL"),
        ("product_progress", 5, "tool_execution", "completed", "ELECTRICAL"),
        ("product_progress", 6, "tool_execution", "skipped", "RADIO"),
        ("product_progress", 7, "tool_execution", "completed", None),
        ("product_progress", 8, "aggregation", "started", None),
    ]


def test_Tool_실행_단계_시작_전_Tool_진행은_보내지_않고_번호도_쓰지_않는다(caplog):
    # 단계 경로와 Tool 경로를 섞지 않음. 빠진 단계 시작을 대신 만들지 않음
    store, context, _ = _running()
    builder = _builder()
    selection = store.update_stage(context, PipelineStage.SELECTION)
    builder.build(selection)

    assert builder.build_tool(selection, ToolName.ELECTRICAL, "started") == []
    assert "Tool 실행 단계 시작 전" in caplog.text
    [next_event, _] = builder.build(store.update_stage(context, PipelineStage.TOOL_EXECUTION))
    assert next_event.sequence == 2


def test_끝난_실행과_진단서_없는_실행의_Tool_진행은_보내지_않는다():
    store, context, _ = _running()
    builder = _builder()
    tool_stage = store.update_stage(context, PipelineStage.TOOL_EXECUTION)
    builder.build(tool_stage)
    builder.build(store.finish(context, build_dummy_assessment("p-1")))

    assert builder.build_tool(tool_stage, ToolName.ELECTRICAL, "completed") == []

    test_session = tool_stage.model_copy(update={
        "context": context.model_copy(update={"diagnosis_id": None, "run_type": RunType.TEST}),
    })
    assert _builder().build_tool(test_session, ToolName.ELECTRICAL, "started") == []


def test_BE_길이_제한을_넘는_진단서는_결과_대신_실패_이벤트로_끝낸다():
    # BE에 보내면 400으로 거절돼 재시도 없이 사라짐 → AI에서 변환 실패로 잡음 (#331)
    class _LongSubjectPresenter(_Presenter):
        def assessment(self, result):
            finding = PublicFindingDto(subject="가" * 256, determination="required", risk_level="high",
                                       summary="요약", rationale="근거")
            return PublicAssessmentDto(
                status="completed", result_status="DIRECT_IMPORT_CERTIFICATION_REQUIRED", summary=result.summary,
                tool_reviews=[PublicToolReviewDto(tool_name="ELECTRICAL", status="COMPLETED", findings=[finding])],
            )

    store, context, _ = _running()

    [event] = _builder(_LongSubjectPresenter()).build(store.finish(context, build_dummy_assessment("p-1")))

    assert (event.event_type, event.error.code, event.error.retryable) == ("product_failed", "AI_PIPELINE_ERROR", False)
