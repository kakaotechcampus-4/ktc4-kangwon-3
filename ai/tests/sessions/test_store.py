"""진단 세션 저장소의 보관·교체·정리 규칙을 확인한다. 상태 전이 규칙은 test_transitions에서."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.errors import InvalidTransitionError
from app.sessions.store import SessionStore
from app.sessions.transitions import AskUser, ChangeStage, Complete, Fail, Resume, Start, apply

START = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class _Clock:
    """테스트용 고정 시계. advance로 시간을 흘림."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def _store(clock: _Clock | None = None) -> SessionStore:
    return SessionStore(retention=timedelta(hours=1), awaiting_retention=timedelta(hours=24), clock=clock or _Clock())


def _session(product_id: str = "p-1", status: SessionStatus = SessionStatus.ACCEPTED) -> DiagnosisSession:
    context = ExecutionContext.start(product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    source = ExtractionInput(product_id=product_id, text_blocks=["상품 설명"])
    return DiagnosisSession(context=context, source=source, status=status, accepted_at=START, updated_at=START)


def test_넣은_세션을_상품_ID로_조회한다():
    store = _store()
    first, second = _session("p-1"), _session("p-2")

    store.add([first, second])

    assert (store.get("p-1"), store.get("p-2"), store.get("p-x")) == (first, second, None)


def test_같은_상품의_세션을_넣으면_새_세션으로_교체한다():
    store = _store()
    store.add([_session("p-1", SessionStatus.COMPLETED)])
    new = _session("p-1")

    store.add([new])

    assert store.get("p-1") is new


def test_같은_실행의_세션에_전이를_적용해_교체한다():
    store = _store()
    session = _session()
    store.add([session])

    transition = store.replace(session.context, lambda current: apply(current, Start(), now=START))

    assert transition.session.status is SessionStatus.RUNNING
    assert store.get("p-1") is transition.session


def test_없는_세션이나_다른_실행의_세션은_바꾸지_않는다():
    # 시간 초과 뒤 같은 상품이 다시 접수되면 옛 스레드의 늦은 갱신은 무시
    store = _store()
    old, new = _session(), _session()
    store.add([new])
    called = []

    assert store.replace(old.context, called.append) is None
    missing = ExecutionContext.start(product_id="p-x", run_type=RunType.PRODUCTION)
    assert store.replace(missing, called.append) is None
    assert called == []
    assert store.get("p-1") is new


def test_전이가_거절되면_세션을_그대로_두고_오류를_넘긴다():
    store = _store()
    session = _session(status=SessionStatus.FAILED)
    store.add([session])

    late = ChangeStage(PipelineStage.VERIFICATION)

    with pytest.raises(InvalidTransitionError):
        store.replace(session.context, lambda current: apply(current, late, now=START))

    assert store.get("p-1") is session


def test_상태별_세션_수를_없는_상태는_0으로_센다():
    store = _store()
    store.add([_session("p-1"), _session("p-2"), _session("p-3", SessionStatus.FAILED)])

    counts = store.count_by_status()

    assert counts == {
        SessionStatus.ACCEPTED: 2, SessionStatus.RUNNING: 0, SessionStatus.AWAITING_INPUT: 0,
        SessionStatus.COMPLETED: 0, SessionStatus.FAILED: 1,
    }


def test_시간_초과_대상은_접수와_실행_중인_세션만이다():
    store = _store()
    store.add([_session(status.value, status) for status in SessionStatus])

    assert {session.status for session in store.unfinished()} == {SessionStatus.ACCEPTED, SessionStatus.RUNNING}


def test_보관_시간이_지난_종료_세션만_지우고_답변_대기는_남긴다():
    clock = _Clock()
    store = _store(clock)
    store.add([_session(status.value, status) for status in SessionStatus])

    clock.advance(minutes=59)
    assert store.purge() == 0

    clock.advance(minutes=1)
    assert store.purge() == 2
    assert store.get(SessionStatus.COMPLETED.value) is None
    assert store.get(SessionStatus.FAILED.value) is None
    assert {status for status in SessionStatus if store.get(status.value)} == {
        SessionStatus.ACCEPTED, SessionStatus.RUNNING, SessionStatus.AWAITING_INPUT,
    }


def test_답변_대기_세션은_자기_보관_시간이_지나면_지운다():
    clock = _Clock()
    store = _store(clock)
    store.add([_session("waiting", SessionStatus.AWAITING_INPUT)])

    clock.advance(hours=23, minutes=59)
    assert store.purge() == 0

    clock.advance(minutes=1)
    assert store.purge() == 1
    assert store.get("waiting") is None


def test_보관_시간은_종료와_답변_대기를_따로_정할_수_있다():
    clock = _Clock()
    store = SessionStore(retention=timedelta(hours=2), awaiting_retention=timedelta(minutes=10), clock=clock)
    store.add([_session("done", SessionStatus.COMPLETED), _session("waiting", SessionStatus.AWAITING_INPUT)])

    clock.advance(minutes=10)

    assert store.purge() == 1
    assert (store.get("waiting"), store.get("done").status) == (None, SessionStatus.COMPLETED)


class _Archive:
    """보관소 호출을 순서대로 기록한다."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def save(self, session: DiagnosisSession) -> None:
        self.calls.append(("save", session.context.product_id, session.status))

    def remove(self, product_ids) -> None:
        self.calls.append(("remove", *product_ids))


def _archived_store(clock: _Clock | None = None) -> tuple[SessionStore, _Archive]:
    archive = _Archive()
    store = SessionStore(retention=timedelta(hours=1), awaiting_retention=timedelta(hours=24),
                         clock=clock or _Clock(), archive=archive)
    return store, archive


def _apply(store: SessionStore, session: DiagnosisSession, change) -> DiagnosisSession:
    return store.replace(session.context, lambda current: apply(current, change, now=START)).session


def test_보관소가_있으면_상태가_바뀔_때만_저장하고_끝나면_지운다():
    store, archive = _archived_store()
    session = _session()

    store.add([session])
    _apply(store, session, Start())
    _apply(store, session, ChangeStage(PipelineStage.EXTRACTION))
    _apply(store, session, ChangeStage(PipelineStage.TOOL_EXECUTION))
    _apply(store, session, Complete(build_dummy_assessment("p-1")))

    # 단계 변경은 상태가 그대로라 기록 안 함
    assert archive.calls == [
        ("save", "p-1", SessionStatus.ACCEPTED),
        ("save", "p-1", SessionStatus.RUNNING),
        ("remove", "p-1"),
    ]


def test_질문으로_끝나면_답변_대기를_저장하고_재접수하면_새_실행으로_덮어쓴다():
    store, archive = _archived_store()
    session = _session()
    store.add([session])
    _apply(store, session, Start())
    result = build_dummy_assessment("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })
    question = PublicQuestionDto(question_key="voltage", question_order=1, question_text="정격 전압은?")
    asked = _apply(store, session, AskUser(result, [question]))
    archive.calls.clear()

    resumed = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    _apply(store, asked, Resume(resumed, []))

    assert archive.calls == [("save", "p-1", SessionStatus.ACCEPTED)]


def test_실패하면_지우고_같은_상품의_새_접수는_덮어쓴다():
    store, archive = _archived_store()
    session = _session()
    store.add([session])
    _apply(store, session, Fail("AI_TIMEOUT", retryable=True))

    store.add([_session()])

    assert archive.calls == [
        ("save", "p-1", SessionStatus.ACCEPTED), ("remove", "p-1"), ("save", "p-1", SessionStatus.ACCEPTED),
    ]


def test_개발용_진단은_보관하지_않는다():
    store, archive = _archived_store()
    context = ExecutionContext.start(product_id="dev-1", run_type=RunType.TEST)
    session = DiagnosisSession(context=context, source=ExtractionInput(product_id="dev-1", text_blocks=["설명"]),
                               accepted_at=START, updated_at=START)

    store.add([session])
    _apply(store, session, Start())

    assert archive.calls == []


def test_보관_시간이_지나_지운_답변_대기_세션은_보관소에서도_지운다():
    clock = _Clock()
    store, archive = _archived_store(clock)
    store.add([_session("p-1", SessionStatus.AWAITING_INPUT), _session("p-2", SessionStatus.COMPLETED)])
    archive.calls.clear()

    clock.advance(hours=24)
    assert store.purge() == 2

    # 끝난 세션은 보관소에 없어 답변 대기만 지움
    assert archive.calls == [("remove", "p-1")]
