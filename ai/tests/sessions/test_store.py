"""진단 세션 저장소의 접수·상태 전이·정리 규칙을 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.schemas.session import SessionStatus
from app.sessions.store import SessionConflictError, SessionStore

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


def _ctx(store: SessionStore, product_id: str) -> ExecutionContext:
    """지금 보관 중인 세션의 실행 컨텍스트. 상태 변경은 이 실행(run_id)으로 요청."""
    return store.get(product_id).context


def _awaiting_result(product_id: str):
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def test_상품마다_실행_컨텍스트를_만들어_접수한다():
    store = _store()

    sessions = store.accept("d-1", ["p-1", "p-2"])

    assert [s.context.product_id for s in sessions] == ["p-1", "p-2"]
    assert all(s.context.diagnosis_id == "d-1" for s in sessions)
    assert all(s.context.run_type is RunType.PRODUCTION for s in sessions)
    assert sessions[0].context.run_id != sessions[1].context.run_id
    assert all(s.status is SessionStatus.ACCEPTED for s in sessions)


@pytest.mark.parametrize("make_active", [
    lambda store: None,                                   # 접수
    lambda store: store.start(_ctx(store, "p-1")),                     # 실행 중
    lambda store: (store.start(_ctx(store, "p-1")), store.finish(_ctx(store, "p-1"), _awaiting_result("p-1"))),  # 답변 대기
])
def test_진행_중인_상품이_섞이면_요청_전체를_거절한다(make_active):
    # #263: 진행 중 상품 포함 시 요청 전체 거절
    store = _store()
    store.accept("d-1", ["p-1"])
    make_active(store)

    with pytest.raises(SessionConflictError) as exc_info:
        store.accept("d-2", ["p-2", "p-1"])

    assert exc_info.value.product_ids == ["p-1"]
    assert store.get("p-2") is None


@pytest.mark.parametrize("finish", [
    lambda store: store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1")),
    lambda store: store.fail(_ctx(store, "p-1"), error_code="AI_PIPELINE_ERROR", retryable=True),
])
def test_끝난_상품은_새_세션으로_다시_접수한다(finish):
    store = _store()
    old = store.accept("d-1", ["p-1"])[0]
    store.start(_ctx(store, "p-1"))
    finish(store)

    new = store.accept("d-2", ["p-1"])[0]

    assert new.status is SessionStatus.ACCEPTED
    assert new.context.run_id != old.context.run_id


def test_실행_중_단계와_시작_시각을_기록한다():
    clock = _Clock()
    store = _store(clock)
    store.accept("d-1", ["p-1"])
    store.start(_ctx(store, "p-1"))
    clock.advance(seconds=5)

    session = store.update_stage(_ctx(store, "p-1"), PipelineStage.EXTRACTION)

    assert session.stage is PipelineStage.EXTRACTION
    assert session.stage_started_at == START + timedelta(seconds=5)
    assert session.updated_at == START + timedelta(seconds=5)


def test_정상_결과는_완료로_기록한다():
    store = _store()
    store.accept("d-1", ["p-1"])
    store.start(_ctx(store, "p-1"))

    session = store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1"))

    assert session.status is SessionStatus.COMPLETED
    assert session.termination_reason is ExecutionEndReason.COMPLETED
    assert session.result is not None


def test_답변이_필요한_결과는_답변_대기로_둔다():
    store = _store()
    store.accept("d-1", ["p-1"])
    store.start(_ctx(store, "p-1"))

    session = store.finish(_ctx(store, "p-1"), _awaiting_result("p-1"))

    assert session.status is SessionStatus.AWAITING_INPUT
    assert session.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED


def test_실패는_종료_사유_없이_오류_코드로만_기록한다():
    # #171 §7.1.1: 미처리 예외를 종료 사유로 바꾸지 않음
    store = _store()
    store.accept("d-1", ["p-1"])
    store.start(_ctx(store, "p-1"))

    session = store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True)

    assert session.status is SessionStatus.FAILED
    assert session.termination_reason is None
    assert (session.error_code, session.retryable) == ("AI_TIMEOUT", True)


def test_대기열에서_실행_전에도_실패로_끝낼_수_있다():
    store = _store()
    store.accept("d-1", ["p-1"])

    assert store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True).status is SessionStatus.FAILED


def test_이미_실패한_세션에_늦게_온_결과는_무시한다():
    # 시간 초과로 실패 처리된 뒤 실행이 끝난 경우
    store = _store()
    store.accept("d-1", ["p-1"])
    store.start(_ctx(store, "p-1"))
    store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True)

    assert store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1")) is None
    assert store.update_stage(_ctx(store, "p-1"), PipelineStage.VERIFICATION) is None
    assert store.get("p-1").status is SessionStatus.FAILED


def test_없는_세션의_상태_변경은_무시한다():
    store = _store()

    missing = ExecutionContext.start(product_id="p-x", run_type=RunType.PRODUCTION)

    assert store.start(missing) is None
    assert store.fail(missing, error_code="AI_TIMEOUT", retryable=True) is None


def test_보관_시간이_지난_종료_세션만_지우고_답변_대기는_남긴다():
    clock = _Clock()
    store = _store(clock)
    store.accept("d-1", ["done", "failed", "waiting", "running"])
    for product_id in ("done", "failed", "waiting", "running"):
        store.start(_ctx(store, product_id))
    store.finish(_ctx(store, "done"), build_dummy_assessment("done"))
    store.fail(_ctx(store, "failed"), error_code="AI_PIPELINE_ERROR", retryable=True)
    store.finish(_ctx(store, "waiting"), _awaiting_result("waiting"))

    clock.advance(minutes=59)
    assert store.purge() == 0

    clock.advance(minutes=1)
    assert store.purge() == 2
    assert store.get("done") is None
    assert store.get("failed") is None
    assert store.get("waiting").status is SessionStatus.AWAITING_INPUT
    assert store.get("running").status is SessionStatus.RUNNING


def test_재접수된_세션은_옛_실행의_컨텍스트로_바꿀_수_없다():
    # 시간 초과 뒤 같은 상품이 다시 접수되면 옛 스레드의 늦은 갱신은 무시
    store = _store()
    store.accept("d-1", ["p-1"])
    old = _ctx(store, "p-1")
    store.start(old)
    store.fail(old, error_code="AI_TIMEOUT", retryable=True)
    store.accept("d-2", ["p-1"])
    store.start(_ctx(store, "p-1"))

    assert store.update_stage(old, PipelineStage.VERIFICATION) is None
    assert store.finish(old, build_dummy_assessment("p-1")) is None
    assert store.fail(old, error_code="AI_PIPELINE_ERROR", retryable=True) is None
    session = store.get("p-1")
    assert session.context.run_id != old.run_id
    assert (session.status, session.stage, session.result) == (SessionStatus.RUNNING, None, None)
