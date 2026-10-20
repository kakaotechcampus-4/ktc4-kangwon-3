"""진단 세션 저장소의 보관·교체·정리 규칙을 확인한다. 상태 전이 규칙은 test_transitions에서."""

from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.store import SessionStore
from app.sessions.transitions import ChangeStage, InvalidTransitionError, Start, apply

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
    return SessionStore(retention=timedelta(hours=1), clock=clock or _Clock())


def _session(product_id: str = "p-1", status: SessionStatus = SessionStatus.ACCEPTED) -> DiagnosisSession:
    context = ExecutionContext.start(product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    return DiagnosisSession(context=context, status=status, accepted_at=START, updated_at=START)


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
