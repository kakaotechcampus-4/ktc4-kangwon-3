"""진단 세션 저장소의 접수·상태 전이·정리 규칙을 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.observability.context import ExecutionContext, PipelineStage, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.schemas.session import SessionStatus
from app.sessions.store import (
    ResumeConflictError,
    SessionConflictError,
    SessionNotFoundError,
    SessionStore,
    UnknownQuestionKeyError,
)

START = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


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


def _inputs(*product_ids: str) -> list[ExtractionInput]:
    return [ExtractionInput(product_id=product_id, text_blocks=["상품 설명"]) for product_id in product_ids]


def _awaiting_result(product_id: str):
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def test_상품마다_실행_컨텍스트를_만들어_접수한다():
    store = _store()

    sessions = store.accept("d-1", _inputs("p-1", "p-2"))

    assert [s.context.product_id for s in sessions] == ["p-1", "p-2"]
    assert all(s.context.diagnosis_id == "d-1" for s in sessions)
    assert all(s.context.run_type is RunType.PRODUCTION for s in sessions)
    assert sessions[0].context.run_id != sessions[1].context.run_id
    assert all(s.status is SessionStatus.ACCEPTED for s in sessions)


def test_접수한_입력을_재진단용으로_보관하고_답변은_비어_있다():
    store = _store()
    source = ExtractionInput(product_id="p-1", text_blocks=["상품 설명"], image_urls=["https://img/1.jpg"])

    [session] = store.accept("d-1", [source])

    assert (store.get("p-1").source, session.answers) == (source, [])


@pytest.mark.parametrize("make_active", [
    lambda store: None,                                   # 접수
    lambda store: store.start(_ctx(store, "p-1")),                     # 실행 중
    lambda store: (store.start(_ctx(store, "p-1")), store.finish(_ctx(store, "p-1"), _awaiting_result("p-1"), _QUESTIONS)),  # 답변 대기
])
def test_진행_중인_상품이_섞이면_요청_전체를_거절한다(make_active):
    # #263: 진행 중 상품 포함 시 요청 전체 거절
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    make_active(store)

    with pytest.raises(SessionConflictError) as exc_info:
        store.accept("d-2", _inputs("p-2", "p-1"))

    assert exc_info.value.product_ids == ["p-1"]
    assert store.get("p-2") is None


@pytest.mark.parametrize("finish", [
    lambda store: store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1")),
    lambda store: store.fail(_ctx(store, "p-1"), error_code="AI_PIPELINE_ERROR", retryable=True),
])
def test_끝난_상품은_새_세션으로_다시_접수한다(finish):
    store = _store()
    old = store.accept("d-1", _inputs("p-1"))[0]
    store.start(_ctx(store, "p-1"))
    finish(store)

    new = store.accept("d-2", _inputs("p-1"))[0]

    assert new.status is SessionStatus.ACCEPTED
    assert new.context.run_id != old.context.run_id


def test_실행_중_단계와_시작_시각을_기록한다():
    clock = _Clock()
    store = _store(clock)
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))
    clock.advance(seconds=5)

    session = store.update_stage(_ctx(store, "p-1"), PipelineStage.EXTRACTION)

    assert session.stage is PipelineStage.EXTRACTION
    assert session.stage_started_at == START + timedelta(seconds=5)
    assert session.updated_at == START + timedelta(seconds=5)


def test_정상_결과는_완료로_기록한다():
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    session = store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1"))

    assert session.status is SessionStatus.COMPLETED
    assert session.termination_reason is ExecutionEndReason.COMPLETED
    assert session.result is not None


def test_답변이_필요한_결과는_답변_대기로_둔다():
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    session = store.finish(_ctx(store, "p-1"), _awaiting_result("p-1"), _QUESTIONS)

    assert session.status is SessionStatus.AWAITING_INPUT
    assert session.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED
    assert (session.question_round, session.questions) == (1, _QUESTIONS)


def test_질문_없이_답변_대기로_끝내지_않는다():
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    with pytest.raises(ValueError):
        store.finish(_ctx(store, "p-1"), _awaiting_result("p-1"))

    assert store.get("p-1").status is SessionStatus.RUNNING


def test_완료는_질문을_넘겨도_기록하지_않는다():
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    session = store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1"), _QUESTIONS)

    assert (session.status, session.question_round, session.questions) == (SessionStatus.COMPLETED, 0, [])


def test_실패는_종료_사유_없이_오류_코드로만_기록한다():
    # #171 §7.1.1: 미처리 예외를 종료 사유로 바꾸지 않음
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    session = store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True)

    assert session.status is SessionStatus.FAILED
    assert session.termination_reason is None
    assert (session.error_code, session.retryable) == ("AI_TIMEOUT", True)


def test_대기열에서_실행_전에도_실패로_끝낼_수_있다():
    store = _store()
    store.accept("d-1", _inputs("p-1"))

    assert store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True).status is SessionStatus.FAILED


def test_이미_실패한_세션에_늦게_온_결과는_무시한다():
    # 시간 초과로 실패 처리된 뒤 실행이 끝난 경우
    store = _store()
    store.accept("d-1", _inputs("p-1"))
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
    store.accept("d-1", _inputs("done", "failed", "waiting", "running"))
    for product_id in ("done", "failed", "waiting", "running"):
        store.start(_ctx(store, product_id))
    store.finish(_ctx(store, "done"), build_dummy_assessment("done"))
    store.fail(_ctx(store, "failed"), error_code="AI_PIPELINE_ERROR", retryable=True)
    store.finish(_ctx(store, "waiting"), _awaiting_result("waiting"), _QUESTIONS)

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
    store.accept("d-1", _inputs("p-1"))
    old = _ctx(store, "p-1")
    store.start(old)
    store.fail(old, error_code="AI_TIMEOUT", retryable=True)
    store.accept("d-2", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))

    assert store.update_stage(old, PipelineStage.VERIFICATION) is None
    assert store.finish(old, build_dummy_assessment("p-1")) is None
    assert store.fail(old, error_code="AI_PIPELINE_ERROR", retryable=True) is None
    session = store.get("p-1")
    assert session.context.run_id != old.run_id
    assert (session.status, session.stage, session.result) == (SessionStatus.RUNNING, None, None)


def _awaiting_session(store: SessionStore, product_id: str = "p-1"):
    """질문으로 끝나 답변을 기다리는 세션."""
    store.accept("d-1", _inputs(product_id))
    store.start(_ctx(store, product_id))
    return store.finish(_ctx(store, product_id), _awaiting_result(product_id), _QUESTIONS)


def _resume(store: SessionStore, waiting, **fields):
    request = {
        "diagnosis_id": "d-1", "product_id": waiting.context.product_id, "run_id": waiting.context.run_id,
        "question_round": waiting.question_round, "answers": {"battery_only": "네"}, **fields,
    }
    return store.resume(**request)


def test_답변_대기_세션을_답변과_함께_새_실행으로_재접수한다():
    clock = _Clock()
    store = _store(clock)
    waiting = _awaiting_session(store)
    clock.advance(minutes=30)

    session = _resume(store, waiting)

    assert session.context.run_id != waiting.context.run_id
    assert (session.context.diagnosis_id, session.context.run_type) == ("d-1", RunType.PRODUCTION)
    assert (session.status, session.stage, session.termination_reason) == (SessionStatus.ACCEPTED, None, None)
    assert [(a.question_round, a.question_key, a.answer_text) for a in session.answers] == [(1, "battery_only", "네")]
    # 시간 초과 기준은 재접수 시각부터
    assert session.accepted_at == START + timedelta(minutes=30)
    assert store.get("p-1") == session


def test_재접수해도_원래_입력과_이전_결과와_질문은_그대로_둔다():
    store = _store()
    waiting = _awaiting_session(store)

    session = _resume(store, waiting)

    assert (session.source, session.result) == (waiting.source, waiting.result)
    assert (session.question_round, session.questions) == (1, _QUESTIONS)


def test_세션이_없으면_재접수하지_않는다():
    store = _store()

    with pytest.raises(SessionNotFoundError):
        store.resume(diagnosis_id="d-1", product_id="p-1", run_id="run-1", question_round=1, answers={"k": "네"})


@pytest.mark.parametrize("finish", [
    lambda store: None,                                                                      # 실행 중
    lambda store: store.finish(_ctx(store, "p-1"), build_dummy_assessment("p-1")),           # 완료
    lambda store: store.fail(_ctx(store, "p-1"), error_code="AI_TIMEOUT", retryable=True),  # 실패
])
def test_답변_대기가_아니면_재접수하지_않는다(finish):
    store = _store()
    store.accept("d-1", _inputs("p-1"))
    store.start(_ctx(store, "p-1"))
    finish(store)
    before = store.get("p-1")

    with pytest.raises(ResumeConflictError):
        store.resume(
            diagnosis_id="d-1", product_id="p-1", run_id=before.context.run_id, question_round=1,
            answers={"battery_only": "네"},
        )

    assert store.get("p-1") == before


@pytest.mark.parametrize("fields", [
    {"run_id": "other-run"},
    {"question_round": 2},
    {"diagnosis_id": "d-2"},
])
def test_기다리는_실행_회차_진단서와_다르면_재접수하지_않는다(fields):
    store = _store()
    waiting = _awaiting_session(store)

    with pytest.raises(ResumeConflictError):
        _resume(store, waiting, **fields)

    assert store.get("p-1") == waiting


def test_같은_답변이_두_번_오면_두_번째는_거절한다():
    # 첫 요청으로 이미 접수 상태라 BE 재시도·중복 요청은 새 실행을 만들지 않음
    store = _store()
    waiting = _awaiting_session(store)
    first = _resume(store, waiting)

    with pytest.raises(ResumeConflictError):
        _resume(store, waiting)

    assert store.get("p-1") == first


def test_이번_회차에_묻지_않은_질문_키가_있으면_거절한다():
    store = _store()
    waiting = _awaiting_session(store)

    with pytest.raises(UnknownQuestionKeyError) as caught:
        _resume(store, waiting, answers={"battery_only": "네", "target_age": "8세"})

    assert caught.value.question_keys == ["target_age"]
    assert store.get("p-1") == waiting


def test_재접수_뒤_질문으로_끝난_실행의_늦은_변경은_무시한다():
    store = _store()
    waiting = _awaiting_session(store)
    _resume(store, waiting)

    assert store.start(waiting.context) is None
    assert store.fail(waiting.context, error_code="AI_TIMEOUT", retryable=True) is None
    assert store.start(_ctx(store, "p-1")).status is SessionStatus.RUNNING
