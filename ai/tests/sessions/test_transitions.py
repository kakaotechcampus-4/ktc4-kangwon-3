"""세션 상태 전이표: 표에 있는 조합만 허용하고, 전이마다 새 세션과 이벤트를 만드는지 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.events import AwaitingInput, Completed, Failed, StageChanged, Started, ToolProgressed
from app.sessions.transitions import (
    STATUS_TRAITS, TRANSITIONS, AskUser, ChangeStage, Complete, Fail, InvalidTransitionError, ReportTool, Start, apply,
)

ACCEPTED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
NOW = ACCEPTED_AT + timedelta(seconds=5)

_COMPLETED = build_dummy_assessment("p-1")
_AWAITING = _COMPLETED.model_copy(update={
    "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
    "verification_status": FinalVerificationStatus.INCOMPLETE,
})
# 일어난 일 종류마다 예시 하나
CHANGES = {
    Start: Start(),
    ChangeStage: ChangeStage(PipelineStage.EXTRACTION),
    ReportTool: ReportTool(ToolName.ELECTRICAL, "started"),
    Complete: Complete(_COMPLETED),
    AskUser: AskUser(_AWAITING),
    Fail: Fail("AI_TIMEOUT", True),
}


def _session(status: SessionStatus = SessionStatus.ACCEPTED, **fields) -> DiagnosisSession:
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    return DiagnosisSession(context=context, status=status, accepted_at=ACCEPTED_AT, updated_at=ACCEPTED_AT, **fields)


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
    finished = {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.AWAITING_INPUT}

    assert not [key for key in TRANSITIONS if key[0] in finished]


def test_실행_시작은_RUNNING으로_바꾸고_Started를_낸다():
    transition = apply(_session(), Start(), now=NOW)

    assert transition.session.status is SessionStatus.RUNNING
    assert transition.session.updated_at == NOW
    assert transition.events == (Started(transition.session),)


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


def test_답변_필요는_답변_대기로_끝낸다():
    transition = apply(_session(SessionStatus.RUNNING), AskUser(_AWAITING), now=NOW)

    session = transition.session
    assert (session.status, session.termination_reason) == (
        SessionStatus.AWAITING_INPUT, ExecutionEndReason.USER_INPUT_REQUIRED,
    )
    assert transition.events == (AwaitingInput(session, _AWAITING),)


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
