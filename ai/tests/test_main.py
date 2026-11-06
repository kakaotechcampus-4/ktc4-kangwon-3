"""서버 기동·종료가 부품을 연결하는지, 운영 부품(production_parts)을 제대로 만드는지 확인한다.

연결 확인은 create_app에 가짜 부품을 넣어 띄움 (진단은 고정 더미, BE는 httpx.MockTransport, DB 없음).
실제 네트워크 요청은 보내지 않는다.
"""

import asyncio
import json
import logging
import threading
import time
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import config, main
from app.clients.backend import BackendCallbackClient
from app.diagnosis import build_questions
from app.agents.base import AgentRunMeta
from app.dummy import job as dummy_job, run_case_diagnosis
from app.observability.agent_sinks import agent_sinks
from app.observability.logs import APP_LOGGER
from app.observability.measurements import ClientCall, measurement_sinks
from app.db import engine as database
from app.routers import _dummy
from app.domain.context import ExecutionContext, RunType
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.manager import SessionManager

TOKEN = "test-internal-token-0123456789abcdef"
_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://mlapi.run/example/v1",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATA_GO_KR_KEY": "test-data-key",
    "KEY_SAFETYKOREA": "test-safety-key",
    "LAW_GO_KR_OC": "test-oc",
    "INTERNAL_API_TOKEN": TOKEN,
    "BE_BASE_URL": "http://be-server:8080",
    "REVIEW_TEXT_HIGH": "0.85",
    "REVIEW_TEXT_LOW": "0.3",
    "REVIEW_IMAGE_HIGH": "0.8",
    "REVIEW_IMAGE_LOW": "0.3",
}


def _wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("조건을 기다리다 시간 초과")
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def _restore_app_logger():
    """lifespan이 붙인 app 로그 핸들러·레벨을 되돌림. 남으면 이 테스트의 stderr 캡처에 계속 씀."""
    logger = logging.getLogger(APP_LOGGER)
    handlers, level = list(logger.handlers), logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)


@pytest.fixture
def fake_be(monkeypatch):
    """실제 ai/.env·DB 없이 기동할 설정을 깔고, 가짜 BE가 받은 콜백 요청 목록을 돌려준다."""
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    # 셸에 SENTRY_DSN이 있어도 테스트 오류를 실제 Sentry로 보내지 않음
    for name in ("DATABASE_URL", "MODEL_PROFILE_OVERRIDES", "AI_DEV_API_ENABLED", "AI_DEV_API_KEY",
                 "SENTRY_DSN", "SENTRY_ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    monkeypatch.setattr(dummy_job, "STAGE_SECONDS", 0)
    for cached in (config.get_settings, database.get_engine, database.get_session_factory):
        cached.cache_clear()
    yield []
    for cached in (config.get_settings, database.get_engine, database.get_session_factory):
        cached.cache_clear()


def _parts(received: list, **overrides) -> main.AppParts:
    """가짜 부품. 진단은 고정 더미(모델·외부 호출 없음), 콜백은 received에 쌓는 가짜 BE, DB 없음."""
    lock = threading.Lock()

    def handler(request):
        with lock:
            received.append(request)
        return httpx.Response(200, json={"code": "OK", "message": "", "data": None})

    parts = {
        "pipeline_job": _dummy.run_dummy_diagnosis,
        "dummy_job": run_case_diagnosis,
        "callback_sender": BackendCallbackClient("http://be-server:8080", TOKEN,
                                                 transport=httpx.MockTransport(handler)),
        "database": None,
        "session_manager": SessionManager,
        "sweep_seconds": config.SESSION_SWEEP_SECONDS,
        "drain_seconds": config.SESSION_DRAIN_SECONDS,
    }
    return main.AppParts(**(parts | overrides))


def _client(parts: main.AppParts, **kwargs) -> TestClient:
    """가짜 부품으로 띄울 앱의 클라이언트. with로 열면 기동, 닫으면 종료."""
    return TestClient(main.create_app(lambda settings: parts), **kwargs)


def test_접수한_상품의_진행과_결과가_BE_콜백으로_나간다(fake_be):
    with _client(_parts(fake_be), headers={"X-Internal-Token": TOKEN}) as client:
        response = client.post("/api/ai/v1/dummy/diagnose/content?case=kc_fan", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        [accepted] = response.json()["data"]["products"]
        _wait_until(lambda: any(json.loads(r.content)["eventType"] == "product_result" for r in fake_be))

    events = [json.loads(request.content) for request in fake_be]
    assert {str(request.url) for request in fake_be} == {"http://be-server:8080/internal/v1/ai/products/p-1"}
    assert {request.headers["X-Internal-Token"] for request in fake_be} == {TOKEN}
    # 접수 응답의 runId로 이 실행의 콜백이 순서대로 나감
    assert {event["runId"] for event in events} == {accepted["runId"]}
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    result = events[-1]
    assert result["eventType"] == "product_result"
    assert result["assessment"]["resultStatus"] == "PURCHASING_AGENT_ALLOWED"


def test_운영_경로로_접수한_상품은_운영_진단_함수로_돌고_결과가_BE_콜백으로_나간다(fake_be):
    with _client(_parts(fake_be), headers={"X-Internal-Token": TOKEN}) as client:
        response = client.post("/api/ai/v1/diagnose/content", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        _wait_until(lambda: any(json.loads(r.content)["eventType"] == "product_result" for r in fake_be))

    assert response.status_code == 202
    # 운영 진단 함수 자리의 고정 더미가 알린 단계가 그대로 콜백으로
    events = [json.loads(request.content) for request in fake_be]
    assert next(event["stage"] for event in events if event["eventType"] == "product_progress") == "extraction"
    assert events[-1]["assessment"]["status"] == "completed"


def test_서버를_끄면_실행_중_진단이_끝날_때까지_기다리고_결과를_BE_콜백으로_보낸다(fake_be):
    started, gate = threading.Event(), threading.Event()

    def slow_job(*args):
        started.set()
        gate.wait(timeout=5)
        return _dummy.run_dummy_diagnosis(*args)

    with _client(_parts(fake_be, pipeline_job=slow_job), headers={"X-Internal-Token": TOKEN}) as client:
        client.post("/api/ai/v1/diagnose/content", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        _wait_until(started.is_set)
        # 종료 처리 중에 진단이 끝나게 함
        threading.Timer(0.2, gate.set).start()

    events = [json.loads(request.content) for request in fake_be]
    assert events[-1]["eventType"] == "product_result"


def test_서버를_끄는_중에도_최대_시간을_넘긴_진단은_시간_초과_실패_콜백으로_끝낸다(fake_be):
    started, gate = threading.Event(), threading.Event()

    def stuck_job(*args):
        started.set()
        gate.wait(timeout=5)
        return _dummy.run_dummy_diagnosis(*args)

    parts = _parts(
        fake_be, pipeline_job=stuck_job, sweep_seconds=0.2, drain_seconds=3,
        session_manager=lambda store, job: SessionManager(store, job, max_duration=timedelta(seconds=1)),
    )
    with _client(parts, headers={"X-Internal-Token": TOKEN}) as client:
        client.post("/api/ai/v1/diagnose/content", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        _wait_until(started.is_set)
        # 접수 1초 뒤 시간 초과. 그보다 늦게 풀어 drain 중에 시간 초과가 나게 함
        threading.Timer(2, gate.set).start()
        manager = client.app.state.session_manager
    # 멈춘 진단 스레드가 다음 테스트까지 남지 않게 끝날 때까지 기다림
    gate.set()
    _wait_until(lambda: manager.snapshot().inflight == 0)

    events = [json.loads(request.content) for request in fake_be]
    failed = [event for event in events if event["eventType"] == "product_failed"]
    assert [(event["error"]["code"], event["error"]["retryable"]) for event in failed] == [("AI_TIMEOUT", True)]


def test_운영_경로는_내부_토큰이_없으면_401이고_접수하지_않는다(fake_be):
    with _client(_parts(fake_be)) as client:
        response = client.post("/api/ai/v1/diagnose/content", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        session = client.app.state.session_manager.get("p-1")

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert session is None
    assert fake_be == []


def test_더미_경로는_내부_토큰이_없으면_401이고_접수하지_않는다(fake_be):
    # 형식이 틀린 요청도 422보다 401이 먼저 (토큰 없이 요청 형식을 떠보지 못하게)
    path = "/api/ai/v1/dummy/diagnose/content"
    with _client(_parts(fake_be)) as client:
        response = client.post(path, json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        malformed = client.post(path, json={"diagnosisId": "d-1"})
        session = client.app.state.session_manager.get("p-1")

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert malformed.status_code == 401
    assert session is None
    assert fake_be == []


def test_샌드박스_진단은_상태_조회로_결과를_보고_BE로는_콜백을_보내지_않는다(fake_be, monkeypatch):
    key = "test-dev-api-key-0123456789abcdefgh"
    monkeypatch.setenv("AI_DEV_API_ENABLED", "true")
    monkeypatch.setenv("AI_DEV_API_KEY", key)
    headers = {"X-Dev-Api-Key": key}

    with _client(_parts(fake_be)) as client:
        accepted = client.post(
            "/api/ai/v1/sandbox/diagnose", json={"products": [{"textBlocks": ["상품 설명"]}]}, headers=headers,
        )
        [product] = accepted.json()["data"]["products"]
        product_id = product["productId"]

        def status():
            return client.get(f"/api/ai/v1/sandbox/diagnose/{product_id}", headers=headers).json()["data"]

        _wait_until(lambda: status()["status"] == "completed")
        done = status()

    assert accepted.status_code == 202
    assert done["assessment"]["status"] == "completed"
    assert done["result"] is not None
    assert fake_be == []


def test_지표_경로가_세션_현황과_끝난_세션을_보여준다(fake_be):
    with _client(_parts(fake_be), headers={"X-Internal-Token": TOKEN}) as client:
        client.post("/api/ai/v1/dummy/diagnose/content?case=kc_fan", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        _wait_until(lambda: 'ai_session_finished_total{outcome="completed",run_type="dummy"} 1.0'
                    in client.get("/metrics").text)
        text = client.get("/metrics").text

    assert 'ai_sessions{status="completed"} 1.0' in text
    assert 'ai_session_accepted_total{run_type="dummy"} 1.0' in text


def test_지표_경로에_받은_HTTP_요청이_라우트_템플릿으로_나온다(fake_be):
    with _client(_parts(fake_be)) as client:
        client.get("/api/ai/v1/health")
        text = client.get("/metrics").text

    assert 'ai_http_requests_total{method="GET",route="/api/ai/v1/health",status="200"} 1.0' in text
    assert 'route="/metrics"' not in text


def test_지표_경로는_처음_만든_시각_시계열을_내보내지_않는다(fake_be):
    with _client(_parts(fake_be)) as client:
        client.get("/api/ai/v1/health")
        text = client.get("/metrics").text

    assert "ai_http_requests_total" in text
    assert "_created" not in text


def test_서버가_떠_있는_동안만_에이전트_호출이_지표에_쌓인다(fake_be):
    meta = AgentRunMeta(component="extraction", model="m", elapsed_ms=100)
    sample = {"component": "extraction", "model": "m", "outcome": "ok"}

    with _client(_parts(fake_be)) as client:
        agent_sinks.publish(meta, "p-1")
        registry = client.app.state.metrics_registry
        text = client.get("/metrics").text
    agent_sinks.publish(meta, "p-2")

    assert 'ai_agent_calls_total{component="extraction",model="m",outcome="ok"} 1.0' in text
    # 종료 때 해제돼 이후 호출은 옛 registry에 쌓이지 않음
    assert registry.get_sample_value("ai_agent_calls_total", sample) == 1.0


def test_서버가_떠_있는_동안만_외부_API_호출이_지표에_쌓인다(fake_be):
    call = ClientCall(api="law", result="ok", seconds=0.1)

    with _client(_parts(fake_be)) as client:
        measurement_sinks.publish(call)
        registry = client.app.state.metrics_registry
        text = client.get("/metrics").text
    measurement_sinks.publish(call)

    assert 'ai_client_calls_total{api="law",result="ok"} 1.0' in text
    assert registry.get_sample_value("ai_client_calls_total", {"api": "law", "result": "ok"}) == 1.0


def test_metrics에_콜백_발신함_대기_수가_나온다(fake_be):
    with _client(_parts(fake_be)) as client:
        text = client.get("/metrics").text

    assert "ai_callback_pending 0.0" in text


class _LawFetchers:
    closed = False

    def close(self):
        self.closed = True


class _Archive:
    """세션 보관소 자리. 기동 때 load가 돌려줄 세션을 정해 두고, 저장·삭제는 상품 ID만 기록한다."""

    def __init__(self, factory=None, saved=()):
        self.factory = factory
        self.saved = list(saved)
        self.calls: list[tuple] = []

    def load(self):
        return self.saved

    def save(self, session):
        self.calls.append(("save", session.context.product_id, session.status.value))

    def remove(self, product_ids):
        self.calls.append(("remove", *product_ids))


def _database(archive: _Archive | None = None, background=(), closed: list | None = None) -> main.AppDatabase:
    """가짜 DB 부품. 종료 때 정리 호출은 closed에 기록."""
    return main.AppDatabase(archive=archive or _Archive(), background=background,
                            close=lambda: closed.append(True) if closed is not None else None)


def test_DB가_있으면_기동_때_예약_작업을_돌리고_종료_때_취소한_뒤_정리한다(fake_be):
    started, cancelled, closed = threading.Event(), [], []

    async def scheduled():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    with _client(_parts(fake_be, database=_database(background=(scheduled,), closed=closed))):
        _wait_until(started.is_set)

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


def test_DB가_있으면_재시작_전_대기_세션은_같은_runId로_다시_돌고_답변_대기는_되살린다(fake_be):
    queued, awaiting = _saved("p-1", SessionStatus.ACCEPTED), _saved("p-2", SessionStatus.AWAITING_INPUT)
    archive = _Archive(saved=[queued, awaiting])

    with _client(_parts(fake_be, database=_database(archive))) as client:
        _wait_until(lambda: any(json.loads(r.content)["eventType"] == "product_result" for r in fake_be))
        manager = client.app.state.session_manager
        restored = manager.get("p-2")

    events = [json.loads(request.content) for request in fake_be]
    assert {(event["productId"], event["runId"]) for event in events} == {("p-1", queued.context.run_id)}
    assert events[-1]["eventType"] == "product_result"
    assert restored == awaiting
    # 다시 돈 세션은 실행 중 → 완료로 보관소에 반영
    assert archive.calls[-2:] == [("save", "p-1", "running"), ("remove", "p-1")]


def test_DB가_있으면_재시작_전_실행_중이던_세션은_기동_때_시간_초과_실패_콜백으로_끝낸다(fake_be):
    running = _saved("p-1", SessionStatus.RUNNING)
    archive = _Archive(saved=[running])

    with _client(_parts(fake_be, database=_database(archive))):
        _wait_until(lambda: fake_be)

    [event] = [json.loads(request.content) for request in fake_be]
    assert (event["eventType"], event["runId"], event["sequence"]) == ("product_failed", running.context.run_id, 1)
    assert (event["error"]["code"], event["error"]["retryable"]) == ("AI_TIMEOUT", True)
    # 저장소에 다시 넣을 때 같은 내용을 한 번 덮어쓰고, 실패로 끝나 지움
    assert archive.calls == [("save", "p-1", "running"), ("remove", "p-1")]


@pytest.fixture
def production(fake_be, monkeypatch):
    """운영 부품 만들기의 바깥 연결(파이프라인 조립·DB·법령 조회)을 기록용으로 바꿈.

    Returns:
        SimpleNamespace: build(설정으로 운영 부품을 만들고 콜백 전송을 닫음), jobs(파이프라인 조립 인자),
            fetchers(법령 조회), refreshed(법령 점검·캐시 정리 호출), law_options(법령 조회 생성 옵션).
    """
    recorded = SimpleNamespace(jobs=[], fetchers=_LawFetchers(), refreshed=[], law_options=[], refresh=[])
    monkeypatch.setattr(main, "build_parts", lambda: "pipeline-parts")
    monkeypatch.setattr(main, "build_job", lambda parts, questions: recorded.jobs.append((parts, questions))
                        or _dummy.run_dummy_diagnosis)
    monkeypatch.setattr(main, "get_session_factory", lambda: "session-factory")
    monkeypatch.setattr(main, "build_law_fetchers", lambda oc, factory, **kwargs: recorded.law_options.append(kwargs)
                        or recorded.fetchers)
    monkeypatch.setattr(main, "refresh_laws",
                        lambda f, sources, **kwargs: recorded.refreshed.append((f, sources, kwargs)))
    monkeypatch.setattr(main, "purge_expired_responses",
                        lambda factory, clients: recorded.refreshed.append((factory, clients)))
    # 예약 작업은 돌리지 않고 넘긴 점검 함수만 받아 둠
    monkeypatch.setattr(main, "run_law_refresh", recorded.refresh.append)
    monkeypatch.setattr(main, "SessionArchiveDatabase", _Archive)

    def build() -> main.AppParts:
        parts = main.production_parts(config.get_settings())
        parts.callback_sender.close()
        return parts

    recorded.build = build
    return recorded


def _init_db(monkeypatch, created=()) -> None:
    monkeypatch.setattr(main, "init_db", lambda: list(created))


def test_운영_부품은_파이프라인을_한_번_조립해_운영_진단_함수로_쓴다(production):
    production.build()

    assert production.jobs == [("pipeline-parts", build_questions)]


def test_운영_부품은_DB_테이블을_만들고_새로_만든_테이블을_로그로_남긴다(production, monkeypatch, caplog):
    _init_db(monkeypatch, created=["api_response_cache", "hs_cases"])

    with caplog.at_level("INFO", logger="app.main"):
        parts = production.build()

    assert "DB 준비 완료 (새로 만든 테이블: api_response_cache, hs_cases)" in caplog.text
    assert parts.database is not None


def test_운영_부품의_법령_점검은_근거_문서를_받고_캐시를_정리하며_정리_때_조회_객체를_닫는다(production, monkeypatch):
    _init_db(monkeypatch)
    database = production.build().database

    database.background[0]()
    [refresh] = production.refresh
    refresh()
    database.close()

    assert production.refreshed == [(production.fetchers, main.LAW_SOURCES,
                                     {"select": main.applied_version, "on_change": main.log_law_changes}),
                                    ("session-factory", ["customs.gw"])]
    assert production.fetchers.closed is True


def test_법령_점검용_조회_객체는_캐시_조회를_측정_기록으로_남기지_않는다(production, monkeypatch):
    _init_db(monkeypatch)

    production.build()

    assert production.law_options == [{"measure": False}]


def test_DATABASE_URL이_없으면_DB_부품_없이_만들고_법령_조회도_만들지_않는다(production, caplog):
    with caplog.at_level("WARNING", logger="app.main"):
        parts = production.build()

    assert parts.database is None
    assert production.law_options == []
    assert "DATABASE_URL 미설정" in caplog.text


def test_DB_준비에_실패해도_경고만_남기고_DB_부품_없이_만든다(production, monkeypatch, caplog):
    def fail():
        raise OperationalError("connect", {}, ConnectionRefusedError("거부됨"))
    monkeypatch.setattr(main, "init_db", fail)

    with caplog.at_level("WARNING", logger="app.main"):
        parts = production.build()

    assert parts.database is None
    assert "DB 준비 실패" in caplog.text
