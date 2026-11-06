"""기동·종료 순서(lifespan)가 부품을 세션 관리자·콜백·지표·DB 보관소에 잇고 종료 때 제대로 닫는지 확인한다.

가짜 부품으로 앱을 띄움 (진단은 고정 더미, BE는 httpx.MockTransport, DB는 가짜 보관소). 실제 네트워크 요청 없음.
"""

import asyncio
import threading
from datetime import timedelta

import pytest

from app.agents.base import AgentRunMeta
from app.domain.context import ExecutionContext, RunType
from app.observability.agent_sinks import agent_sinks
from app.observability.measurements import ClientCall, measurement_sinks
from app.routers import _dummy
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.manager import SessionManager
from app.startup.parts import AppDatabase
from tests.app_harness import TOKEN, FakeBackend, app_env, client, fake_parts, wait_until

PRODUCT = {"diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}]}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    yield from app_env(monkeypatch)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


def _results(backend: FakeBackend) -> bool:
    return any(event["eventType"] == "product_result" for event in backend.events)


def test_접수한_상품의_진행과_결과가_BE_콜백으로_나간다(backend):
    with client(fake_parts(backend), headers={"X-Internal-Token": TOKEN}) as app:
        response = app.post("/api/ai/v1/dummy/diagnose/content?case=kc_fan", json=PRODUCT)
        [accepted] = response.json()["data"]["products"]
        wait_until(lambda: _results(backend))

    events = backend.events
    assert {str(request.url) for request in backend.requests} == {"http://be-server:8080/internal/v1/ai/products/p-1"}
    assert {request.headers["X-Internal-Token"] for request in backend.requests} == {TOKEN}
    # 접수 응답의 runId로 이 실행의 콜백이 순서대로 나감
    assert {event["runId"] for event in events} == {accepted["runId"]}
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    result = events[-1]
    assert result["eventType"] == "product_result"
    assert result["assessment"]["resultStatus"] == "PURCHASING_AGENT_ALLOWED"


def test_운영_경로로_접수한_상품은_운영_진단_함수로_돌고_결과가_BE_콜백으로_나간다(backend):
    with client(fake_parts(backend), headers={"X-Internal-Token": TOKEN}) as app:
        response = app.post("/api/ai/v1/diagnose/content", json=PRODUCT)
        wait_until(lambda: _results(backend))

    assert response.status_code == 202
    # 운영 진단 함수 자리의 고정 더미가 알린 단계가 그대로 콜백으로
    events = backend.events
    assert next(event["stage"] for event in events if event["eventType"] == "product_progress") == "extraction"
    assert events[-1]["assessment"]["status"] == "completed"


def test_서버를_끄면_실행_중_진단이_끝날_때까지_기다리고_결과를_BE_콜백으로_보낸다(backend):
    started, gate = threading.Event(), threading.Event()

    def slow_job(*args):
        started.set()
        gate.wait(timeout=5)
        return _dummy.run_dummy_diagnosis(*args)

    with client(fake_parts(backend, pipeline_job=slow_job), headers={"X-Internal-Token": TOKEN}) as app:
        app.post("/api/ai/v1/diagnose/content", json=PRODUCT)
        wait_until(started.is_set)
        # 종료 처리 중에 진단이 끝나게 함
        threading.Timer(0.2, gate.set).start()

    assert backend.events[-1]["eventType"] == "product_result"


def test_서버를_끄는_중에도_최대_시간을_넘긴_진단은_시간_초과_실패_콜백으로_끝낸다(backend):
    started, gate = threading.Event(), threading.Event()

    def stuck_job(*args):
        started.set()
        gate.wait(timeout=5)
        return _dummy.run_dummy_diagnosis(*args)

    parts = fake_parts(
        backend, pipeline_job=stuck_job, sweep_seconds=0.2, drain_seconds=3,
        session_manager=lambda store, job: SessionManager(store, job, max_duration=timedelta(seconds=1)),
    )
    with client(parts, headers={"X-Internal-Token": TOKEN}) as app:
        app.post("/api/ai/v1/diagnose/content", json=PRODUCT)
        wait_until(started.is_set)
        # 접수 1초 뒤 시간 초과. 그보다 늦게 풀어 drain 중에 시간 초과가 나게 함
        threading.Timer(2, gate.set).start()
        manager = app.app.state.session_manager
    # 멈춘 진단 스레드가 다음 테스트까지 남지 않게 끝날 때까지 기다림
    gate.set()
    wait_until(lambda: manager.snapshot().inflight == 0)

    failed = [event for event in backend.events if event["eventType"] == "product_failed"]
    assert [(event["error"]["code"], event["error"]["retryable"]) for event in failed] == [("AI_TIMEOUT", True)]


def test_샌드박스_진단은_상태_조회로_결과를_보고_BE로는_콜백을_보내지_않는다(backend, monkeypatch):
    key = "test-dev-api-key-0123456789abcdefgh"
    monkeypatch.setenv("AI_DEV_API_ENABLED", "true")
    monkeypatch.setenv("AI_DEV_API_KEY", key)
    headers = {"X-Dev-Api-Key": key}

    with client(fake_parts(backend)) as app:
        accepted = app.post(
            "/api/ai/v1/sandbox/diagnose", json={"products": [{"textBlocks": ["상품 설명"]}]}, headers=headers,
        )
        [product] = accepted.json()["data"]["products"]
        product_id = product["productId"]

        def status():
            return app.get(f"/api/ai/v1/sandbox/diagnose/{product_id}", headers=headers).json()["data"]

        wait_until(lambda: status()["status"] == "completed")
        done = status()

    assert accepted.status_code == 202
    assert done["assessment"]["status"] == "completed"
    assert done["result"] is not None
    assert backend.requests == []


def test_지표_경로가_세션_현황과_끝난_세션을_보여준다(backend):
    with client(fake_parts(backend), headers={"X-Internal-Token": TOKEN}) as app:
        app.post("/api/ai/v1/dummy/diagnose/content?case=kc_fan", json=PRODUCT)
        wait_until(lambda: 'ai_session_finished_total{outcome="completed",run_type="dummy"} 1.0'
                   in app.get("/metrics").text)
        text = app.get("/metrics").text

    assert 'ai_sessions{status="completed"} 1.0' in text
    assert 'ai_session_accepted_total{run_type="dummy"} 1.0' in text


def test_지표_경로는_처음_만든_시각_시계열을_내보내지_않는다(backend):
    with client(fake_parts(backend)) as app:
        app.get("/api/ai/v1/health")
        text = app.get("/metrics").text

    assert "ai_http_requests_total" in text
    assert "_created" not in text


def test_서버가_떠_있는_동안만_에이전트_호출이_지표에_쌓인다(backend):
    meta = AgentRunMeta(component="extraction", model="m", elapsed_ms=100)
    sample = {"component": "extraction", "model": "m", "outcome": "ok"}

    with client(fake_parts(backend)) as app:
        agent_sinks.publish(meta, "p-1")
        registry = app.app.state.metrics_registry
        text = app.get("/metrics").text
    agent_sinks.publish(meta, "p-2")

    assert 'ai_agent_calls_total{component="extraction",model="m",outcome="ok"} 1.0' in text
    # 종료 때 해제돼 이후 호출은 옛 registry에 쌓이지 않음
    assert registry.get_sample_value("ai_agent_calls_total", sample) == 1.0


def test_서버가_떠_있는_동안만_외부_API_호출이_지표에_쌓인다(backend):
    call = ClientCall(api="law", result="ok", seconds=0.1)

    with client(fake_parts(backend)) as app:
        measurement_sinks.publish(call)
        registry = app.app.state.metrics_registry
        text = app.get("/metrics").text
    measurement_sinks.publish(call)

    assert 'ai_client_calls_total{api="law",result="ok"} 1.0' in text
    assert registry.get_sample_value("ai_client_calls_total", {"api": "law", "result": "ok"}) == 1.0


def test_metrics에_콜백_발신함_대기_수가_나온다(backend):
    with client(fake_parts(backend)) as app:
        text = app.get("/metrics").text

    assert "ai_callback_pending 0.0" in text


class _Archive:
    """세션 보관소 자리. 기동 때 load가 돌려줄 세션을 정해 두고, 저장·삭제는 상품 ID만 기록한다."""

    def __init__(self, saved=()):
        self.saved = list(saved)
        self.calls: list[tuple] = []

    def load(self):
        return self.saved

    def save(self, session):
        self.calls.append(("save", session.context.product_id, session.status.value))

    def remove(self, product_ids):
        self.calls.append(("remove", *product_ids))


def _database(archive: _Archive | None = None, background=(), closed: list | None = None) -> AppDatabase:
    """가짜 DB 부품. 종료 때 정리 호출은 closed에 기록."""
    return AppDatabase(archive=archive or _Archive(), background=background,
                       close=lambda: closed.append(True) if closed is not None else None)


def test_DB가_있으면_기동_때_예약_작업을_돌리고_종료_때_취소한_뒤_정리한다(backend):
    started, cancelled, closed = threading.Event(), [], []

    async def scheduled():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    with client(fake_parts(backend, database=_database(background=(scheduled,), closed=closed))):
        wait_until(started.is_set)

    assert (cancelled, closed) == ([True], [True])


def _saved(product_id: str, status: SessionStatus) -> DiagnosisSession:
    """재시작 전에 보관된 세션. 답변 대기면 질문 1회차를 보낸 상태."""
    context = ExecutionContext.start(product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id="d-1")
    source = ExtractionInput(product_id=product_id, text_blocks=["상품 설명"])
    if status is not SessionStatus.AWAITING_INPUT:
        return DiagnosisSession(context=context, source=source, status=status)
    question = PublicQuestionDto(question_key="voltage", question_order=1, question_text="정격 전압은?")
    return DiagnosisSession(context=context, source=source, status=status, question_round=1, questions=[question],
                            result=_dummy.build_dummy_assessment(product_id))


def test_DB가_있으면_재시작_전_대기_세션은_같은_runId로_다시_돌고_답변_대기는_되살린다(backend):
    queued, awaiting = _saved("p-1", SessionStatus.ACCEPTED), _saved("p-2", SessionStatus.AWAITING_INPUT)
    archive = _Archive(saved=[queued, awaiting])

    with client(fake_parts(backend, database=_database(archive))) as app:
        wait_until(lambda: _results(backend))
        restored = app.app.state.session_manager.get("p-2")

    events = backend.events
    assert {(event["productId"], event["runId"]) for event in events} == {("p-1", queued.context.run_id)}
    assert events[-1]["eventType"] == "product_result"
    assert restored == awaiting
    # 다시 돈 세션은 실행 중 → 완료로 보관소에 반영
    assert archive.calls[-2:] == [("save", "p-1", "running"), ("remove", "p-1")]


def test_DB가_있으면_재시작_전_실행_중이던_세션은_기동_때_시간_초과_실패_콜백으로_끝낸다(backend):
    running = _saved("p-1", SessionStatus.RUNNING)
    archive = _Archive(saved=[running])

    with client(fake_parts(backend, database=_database(archive))):
        wait_until(lambda: backend.requests)

    [event] = backend.events
    assert (event["eventType"], event["runId"], event["sequence"]) == ("product_failed", running.context.run_id, 1)
    assert (event["error"]["code"], event["error"]["retryable"]) == ("AI_TIMEOUT", True)
    # 저장소에 다시 넣을 때 같은 내용을 한 번 덮어쓰고, 실패로 끝나 지움
    assert archive.calls == [("save", "p-1", "running"), ("remove", "p-1")]
