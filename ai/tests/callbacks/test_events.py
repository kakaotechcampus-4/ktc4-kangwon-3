"""세션 이벤트 → 콜백 이벤트 변환을 전이표가 실제로 내는 이벤트로 확인한다."""

from itertools import count

import pytest

from app.callbacks.events import EventBuilder
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.base import utc_now
from app.schemas.callback import PublicAssessmentDto, PublicFindingDto, PublicQuestionDto, PublicToolReviewDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import DiagnosisSession
from app.sessions.events import SessionEvent, Started, ToolProgressed
from app.sessions.transitions import AskUser, Change, ChangeStage, Complete, Fail, ReportTool, Resume, Start, apply


_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


class _Presenter:
    """고정 진단서를 돌려주는 가짜 변환기."""

    def assessment(self, result):
        return PublicAssessmentDto(status="completed", result_status="DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                                   summary=result.summary)


class _BrokenPresenter(_Presenter):
    def assessment(self, result):
        raise ValueError("변환 실패")


def _builder(presenter=None) -> EventBuilder:
    ids = count(1)
    return EventBuilder(presenter or _Presenter(), new_event_id=lambda: f"e-{next(ids)}")


class _Run:
    """전이표대로 바꿔 가며 그 전이가 낸 세션 이벤트를 돌려주는 실행 하나. 실행기 없이 세션 이벤트를 재현."""

    def __init__(self, product_id: str = "p-1") -> None:
        now = utc_now()
        self.context = ExecutionContext.start(product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id="d-1")
        self.session = DiagnosisSession(
            context=self.context, source=ExtractionInput(product_id=product_id, text_blocks=["상품 설명"]),
            accepted_at=now, updated_at=now,
        )

    def __call__(self, change: Change) -> SessionEvent:
        [event] = apply(self.session, change, now=utc_now()).events
        self.session = event.session
        return event


def _running(product_id: str = "p-1") -> tuple[_Run, ExecutionContext, SessionEvent]:
    run = _Run(product_id)
    return run, run.context, run(Start())


def _awaiting(product_id: str):
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def _summary(events) -> list[tuple]:
    return [(event.event_type, event.sequence, getattr(event, "stage", None), getattr(event, "stage_status", None))
            for event in events]


def test_단계가_바뀌면_앞_단계_완료와_새_단계_시작을_순서대로_만든다():
    run, context, started = _running()
    builder = _builder()

    events = [*builder.build(started),
              *builder.build(run(ChangeStage(PipelineStage.EXTRACTION))),
              *builder.build(run(ChangeStage(PipelineStage.SELECTION))),
              *builder.build(run(Complete(build_dummy_assessment("p-1"))))]

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
    run, context, started = _running()
    builder = _builder()

    assert builder.build(started) == []
    assert builder.build(run(ChangeStage(PipelineStage.PIPELINE))) == []
    assert len(builder.build(run(ChangeStage(PipelineStage.EXTRACTION)))) == 1
    assert builder.build(run(ChangeStage(PipelineStage.EXTRACTION))) == []


def test_답변_대기는_세션에_기록된_회차와_질문으로_질문_이벤트를_보낸다():
    run, context, _ = _running()

    [event] = _builder().build(run(AskUser(_awaiting("p-1"), _QUESTIONS)))

    assert (event.event_type, event.question_round, event.questions) == ("product_awaiting_input", 1, _QUESTIONS)


def _resumed() -> tuple[_Run, SessionEvent]:
    """답변 대기 뒤 새 실행으로 재접수한 실행과 그 재접수 이벤트."""
    run, context, _ = _running()
    run(AskUser(_awaiting("p-1"), _QUESTIONS))
    new_context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    return run, run(Resume(new_context, []))


def test_재접수는_이벤트를_만들지_않고_새_실행은_1번부터_보낸다():
    run, resumed = _resumed()
    builder = _builder()

    assert builder.build(resumed) == []
    builder.build(run(Start()))
    [event] = builder.build(run(ChangeStage(PipelineStage.EXTRACTION)))

    assert (event.run_id, event.sequence) == (resumed.session.context.run_id, 1)


def test_실패와_시간_초과는_마지막_단계와_공개_문구로_보낸다():
    run, context, _ = _running()
    builder = _builder()
    builder.build(run(ChangeStage(PipelineStage.TOOL_EXECUTION)))

    [event] = builder.build(run(Fail("AI_TIMEOUT", retryable=True)))

    assert (event.event_type, event.sequence, event.stage) == ("product_failed", 2, "tool_execution")
    assert (event.error.code, event.error.message, event.error.retryable) == (
        "AI_TIMEOUT", "진단 시간이 초과되었습니다.", True)


def test_대기_중_시간_초과는_단계_없이_실패로_보낸다():
    run = _Run()

    [event] = _builder().build(run(Fail("AI_TIMEOUT", retryable=True)))

    assert (event.sequence, event.stage) == (1, None)


def test_모르는_오류_코드는_기본_문구로_보낸다():
    run, context, _ = _running()

    [event] = _builder().build(run(Fail("SOMETHING_NEW", retryable=False)))

    assert (event.error.code, event.error.message) == ("SOMETHING_NEW", "진단 실행 중 오류가 발생했습니다.")


def test_끝난_실행의_늦은_변경은_이벤트를_만들지_않는다():
    run, context, _ = _running()
    builder = _builder()
    finished = run(Complete(build_dummy_assessment("p-1")))
    builder.build(finished)

    # 같은 변경이 두 번 전달돼도 결과 이벤트는 한 번
    assert builder.build(finished) == []


def test_실행마다_sequence를_1부터_따로_센다():
    builder = _builder()
    first_run, first, first_started = _running("p-1")
    second_run, second, _ = _running("p-2")

    builder.build(first_run(ChangeStage(PipelineStage.EXTRACTION)))
    [other] = builder.build(second_run(ChangeStage(PipelineStage.EXTRACTION)))

    assert (other.run_id, other.sequence) == (second.run_id, 1)


def test_진단서_없는_실행은_보내지_않는다():
    run, context, started = _running()
    session = started.session.model_copy(update={
        "context": context.model_copy(update={"diagnosis_id": None, "run_type": RunType.TEST}),
    })

    assert _builder().build(Started(session)) == []


def test_진단서_변환이_실패하면_실패_이벤트로_끝낸다(caplog):
    # 마지막 이벤트가 빠지면 BE에서 진행 중으로 남음
    run, context, _ = _running()
    builder = _builder(_BrokenPresenter())
    builder.build(run(ChangeStage(PipelineStage.EXTRACTION)))

    [event] = builder.build(run(Complete(build_dummy_assessment("p-1"))))

    assert (event.event_type, event.sequence, event.stage) == ("product_failed", 2, "extraction")
    assert (event.error.code, event.error.retryable) == ("AI_PIPELINE_ERROR", False)
    assert "변환 실패" in caplog.text


def test_변환_실패로_끝난_실행의_늦은_변경은_이벤트를_만들지_않는다():
    run, context, _ = _running()
    builder = _builder(_BrokenPresenter())
    finished = run(Complete(build_dummy_assessment("p-1")))
    builder.build(finished)

    # 같은 변경이 다시 와도 실패 이벤트는 한 번
    builder._presenter = _Presenter()
    assert builder.build(finished) == []


def test_Tool_진행은_단계_이벤트에_이어_번호를_매기고_공개_이름으로_보낸다():
    run, context, _ = _running()
    builder = _builder()

    events = [*builder.build(run(ChangeStage(PipelineStage.SELECTION))),
              *builder.build(run(ChangeStage(PipelineStage.TOOL_EXECUTION))),
              *builder.build(run(ReportTool(ToolName.ELECTRICAL, "started"))),
              *builder.build(run(ReportTool(ToolName.ELECTRICAL, "completed"))),
              *builder.build(run(ReportTool(ToolName.RADIO, "skipped"))),
              *builder.build(run(ChangeStage(PipelineStage.AGGREGATION)))]

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
    run, context, _ = _running()
    builder = _builder()
    builder.build(run(ChangeStage(PipelineStage.SELECTION)))

    assert builder.build(run(ReportTool(ToolName.ELECTRICAL, "started"))) == []
    assert "Tool 실행 단계 시작 전" in caplog.text
    [next_event, _] = builder.build(run(ChangeStage(PipelineStage.TOOL_EXECUTION)))
    assert next_event.sequence == 2


def test_끝난_실행과_진단서_없는_실행의_Tool_진행은_보내지_않는다():
    run, context, _ = _running()
    builder = _builder()
    tool_stage = run(ChangeStage(PipelineStage.TOOL_EXECUTION))
    builder.build(tool_stage)
    builder.build(run(Complete(build_dummy_assessment("p-1"))))

    # 끝난 뒤에는 전이표가 Tool 진행을 거절하므로 이벤트를 직접 만듦 (늦게 도착한 경우 재현)
    assert builder.build(ToolProgressed(tool_stage.session, ToolName.ELECTRICAL, "completed")) == []

    test_session = tool_stage.session.model_copy(update={
        "context": context.model_copy(update={"diagnosis_id": None, "run_type": RunType.TEST}),
    })
    assert _builder().build(ToolProgressed(test_session, ToolName.ELECTRICAL, "started")) == []


def _every_event_kind() -> list[type[SessionEvent]]:
    """SessionEvent의 하위 종류 전부 (손자 포함)."""
    kinds, pending = [], [SessionEvent]
    while pending:
        for kind in pending.pop().__subclasses__():
            kinds.append(kind)
            pending.append(kind)
    return kinds


def _event_examples() -> dict[type[SessionEvent], SessionEvent]:
    """세션 이벤트 종류마다 전이표가 실제로 내는 예시 하나."""
    run, _, started = _running()
    examples = [started, run(ChangeStage(PipelineStage.TOOL_EXECUTION)), run(ReportTool(ToolName.RADIO, "started"))]
    examples += [_running()[0](change) for change in (
        Complete(build_dummy_assessment("p-1")), AskUser(_awaiting("p-1"), _QUESTIONS), Fail("AI_TIMEOUT", retryable=True),
    )]
    examples.append(_resumed()[1])
    return {type(event): event for event in examples}


def test_모든_세션_이벤트_종류에_예시가_있다():
    # 새 이벤트 종류를 추가하면 예시도 넣어야 아래 전수 검사가 그 종류까지 확인함
    assert set(_every_event_kind()) <= set(_event_examples())


@pytest.mark.parametrize("kind", _every_event_kind(), ids=lambda kind: kind.__name__)
def test_모든_세션_이벤트_종류를_처리한다(kind):
    # 처리를 빠뜨린 종류는 TypeError
    _builder().build(_event_examples()[kind])


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

    run, context, _ = _running()

    [event] = _builder(_LongSubjectPresenter()).build(run(Complete(build_dummy_assessment("p-1"))))

    assert (event.event_type, event.error.code, event.error.retryable) == ("product_failed", "AI_PIPELINE_ERROR", False)
