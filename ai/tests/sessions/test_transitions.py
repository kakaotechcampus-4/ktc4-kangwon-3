"""세션 상태 전이표: 표에 있는 조합만 허용하고, 전이마다 새 세션과 이벤트를 만드는지 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.session import DiagnosisSession, SessionAnswer, SessionStatus
from app.sessions.events import AwaitingInput, Completed, Failed, Resumed, StageChanged, Started, ToolProgressed
from app.sessions.transitions import (
    STATUS_TRAITS, TRANSITIONS, AskUser, ChangeStage, Complete, Fail, InvalidTransitionError, ReportTool, Resume,
    Start, apply,
)

ACCEPTED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
NOW = ACCEPTED_AT + timedelta(seconds=5)

_COMPLETED = build_dummy_assessment("p-1")
_AWAITING = _COMPLETED.model_copy(update={
    "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
    "verification_status": FinalVerificationStatus.INCOMPLETE,
})
_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]
_ANSWERS = [SessionAnswer(question_round=1, question_key="battery_only", answer_text="네")]
_NEW_CONTEXT = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
# 일어난 일 종류마다 예시 하나
CHANGES = {
    Start: Start(),
    ChangeStage: ChangeStage(PipelineStage.EXTRACTION),
    ReportTool: ReportTool(ToolName.ELECTRICAL, "started"),
    Complete: Complete(_COMPLETED),
    AskUser: AskUser(_AWAITING, _QUESTIONS),
    Resume: Resume(_NEW_CONTEXT, _ANSWERS),
    Fail: Fail("AI_TIMEOUT", True),
}


def _session(status: SessionStatus = SessionStatus.ACCEPTED, **fields) -> DiagnosisSession:
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    source = ExtractionInput(product_id="p-1", text_blocks=["상품 설명"])
    return DiagnosisSession(
        context=context, source=source, status=status, accepted_at=ACCEPTED_AT, updated_at=ACCEPTED_AT, **fields,
    )


@pytest.mark.parametrize("status", list(SessionStatus))
@pytest.mark.parametrize("kind", list(CHANGES))
def test_표에_있는_조합만_허용하고_나머지는_거절한다(status, kind):
    session = _session(status)
    expected = TRANSITIONS.get((status, kind))

    if expected is None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            apply(session, CHANGES[kind], now=NOW)
        assert (exc_info.value.status, exc_info.value.change) == (status, CHANGES[kind])
    else:
        assert apply(session, CHANGES[kind], now=NOW).session.status is expected


def test_규칙표의_모든_일에_전수_검사용_예시가_있다():
    # 새 일을 표에 추가하면 CHANGES에도 예시를 넣어야 위 전수 검사가 그 일까지 확인함
    assert {kind for _, kind in TRANSITIONS} <= set(CHANGES)


def test_모든_상태의_성격이_정해져_있다():
    assert set(STATUS_TRAITS) == set(SessionStatus)


def test_끝난_세션에는_어떤_일도_적용되지_않는다():
    finished = {SessionStatus.COMPLETED, SessionStatus.FAILED}

    assert not [key for key in TRANSITIONS if key[0] in finished]


def test_답변_대기에서는_재접수만_할_수_있다():
    assert [kind for status, kind in TRANSITIONS if status is SessionStatus.AWAITING_INPUT] == [Resume]


def test_실행_시작은_RUNNING으로_바꾸고_시작_시각을_기록하고_Started를_낸다():
    transition = apply(_session(), Start(), now=NOW)

    assert transition.session.status is SessionStatus.RUNNING
    assert (transition.session.started_at, transition.session.updated_at) == (NOW, NOW)
    assert transition.events == (Started(transition.session),)


def test_실행_시작_시각은_이후_변경에도_유지한다():
    started = apply(_session(), Start(), now=NOW).session
    later = NOW + timedelta(seconds=30)

    staged = apply(started, ChangeStage(PipelineStage.EXTRACTION), now=later).session
    finished = apply(staged, Complete(_COMPLETED), now=later).session

    assert (finished.started_at, finished.updated_at) == (NOW, later)


def test_단계_변경은_단계와_단계_시작_시각을_기록한다():
    transition = apply(_session(SessionStatus.RUNNING), ChangeStage(PipelineStage.SELECTION), now=NOW)

    assert (transition.session.stage, transition.session.stage_started_at) == (PipelineStage.SELECTION, NOW)
    assert transition.events == (StageChanged(transition.session, PipelineStage.SELECTION),)


def test_Tool_진행은_세션을_바꾸지_않고_이벤트만_낸다():
    session = _session(SessionStatus.RUNNING, stage=PipelineStage.TOOL_EXECUTION)

    transition = apply(session, ReportTool(ToolName.RADIO, "completed"), now=NOW)

    assert transition.session is session
    assert transition.events == (ToolProgressed(session, ToolName.RADIO, "completed"),)


def test_완료는_결과와_종료_사유를_기록한다():
    transition = apply(_session(SessionStatus.RUNNING), Complete(_COMPLETED), now=NOW)

    session = transition.session
    assert (session.status, session.result, session.termination_reason) == (
        SessionStatus.COMPLETED, _COMPLETED, _COMPLETED.termination_reason,
    )
    assert transition.events == (Completed(session, _COMPLETED),)


def test_답변_필요는_답변_대기로_끝내고_회차를_올려_질문을_기록한다():
    transition = apply(_session(SessionStatus.RUNNING), AskUser(_AWAITING, _QUESTIONS), now=NOW)

    session = transition.session
    assert (session.status, session.termination_reason) == (
        SessionStatus.AWAITING_INPUT, ExecutionEndReason.USER_INPUT_REQUIRED,
    )
    assert (session.question_round, session.questions) == (1, _QUESTIONS)
    assert transition.events == (AwaitingInput(session, _AWAITING),)


def _question(key: str, order: int) -> PublicQuestionDto:
    return PublicQuestionDto(question_key=key, question_order=order, question_text=f"{key} 질문")


@pytest.mark.parametrize(("questions", "message"), [
    ([], "질문이 필요"),
    ([_question("battery_only", 1), _question("battery_only", 2)], "질문 키가 겹칩니다"),
    ([_question("battery_only", 1), _question("target_age", 1)], "질문 순서가 겹칩니다"),
])
def test_질문이_없거나_겹치면_답변_대기로_두지_않는다(questions, message):
    # 질문 콜백 검증에서 걸리면 BE는 질문을 못 받은 채 기다리게 됨
    with pytest.raises(ValueError, match=message):
        apply(_session(SessionStatus.RUNNING), AskUser(_AWAITING, questions), now=NOW)


def test_2회차는_지난_회차에_물은_질문_키를_다시_쓰지_않는다():
    session = _session(SessionStatus.RUNNING, question_round=1, questions=_QUESTIONS)

    with pytest.raises(ValueError, match="battery_only"):
        apply(session, AskUser(_AWAITING, _QUESTIONS), now=NOW)

    second = apply(session, AskUser(_AWAITING, [_question("target_age", 1)]), now=NOW).session
    assert (second.question_round, [q.question_key for q in second.questions]) == (2, ["target_age"])


def test_재접수는_새_실행으로_접수_상태가_되고_답변을_쌓는다():
    waiting = apply(
        apply(apply(_session(), Start(), now=NOW).session, ChangeStage(PipelineStage.AGGREGATION), now=NOW).session,
        AskUser(_AWAITING, _QUESTIONS), now=NOW,
    ).session
    later = NOW + timedelta(minutes=30)

    transition = apply(waiting, Resume(_NEW_CONTEXT, _ANSWERS), now=later)

    session = transition.session
    assert session.context == _NEW_CONTEXT
    assert (session.status, session.stage, session.termination_reason) == (SessionStatus.ACCEPTED, None, None)
    # 시간 초과 기준·대기 시간은 재접수 시각부터
    assert (session.accepted_at, session.started_at, session.stage_started_at) == (later, None, None)
    assert session.answers == _ANSWERS
    # 원래 입력·이전 결과·질문은 그대로 (재진단 입력과 2회차 키 검사에 씀)
    assert (session.source, session.result, session.question_round, session.questions) == (
        waiting.source, _AWAITING, 1, _QUESTIONS,
    )
    assert transition.events == (Resumed(session),)


@pytest.mark.parametrize("status", [SessionStatus.ACCEPTED, SessionStatus.RUNNING])
def test_실패는_종료_사유_대신_오류_코드로_기록한다(status):
    transition = apply(_session(status), Fail("AI_PIPELINE_ERROR", False), now=NOW)

    session = transition.session
    assert (session.status, session.error_code, session.retryable, session.termination_reason) == (
        SessionStatus.FAILED, "AI_PIPELINE_ERROR", False, None,
    )
    assert transition.events == (Failed(session, "AI_PIPELINE_ERROR", False),)


def test_원래_세션은_바뀌지_않는다():
    session = _session()
    before = session.model_dump()

    transition = apply(session, Start(), now=NOW)

    assert transition.session is not session
    assert session.model_dump() == before


def test_실행_컨텍스트와_접수_시각은_유지한다():
    session = _session()

    transition = apply(session, Start(), now=NOW)

    assert (transition.session.context, transition.session.accepted_at) == (session.context, ACCEPTED_AT)


def test_변경_시각은_UTC로_정규화한다():
    kst = timezone(timedelta(hours=9))

    transition = apply(_session(), Start(), now=NOW.astimezone(kst))

    assert transition.session.updated_at.tzinfo == timezone.utc
    assert transition.session.updated_at == NOW
