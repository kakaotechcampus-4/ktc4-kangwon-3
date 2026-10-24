"""서버 lifespan이 진단 세션 관리자에 BE 콜백 발신함을 연결하는지 확인한다.

가짜 BE는 httpx.MockTransport. 실제 네트워크 요청은 보내지 않는다.
"""

import json
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, database, main
from app.callbacks import HttpCallbackSender
from app.agents.base import AgentRunMeta
from app.observability.agent_sinks import agent_sinks
from app.routers import _dummy

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
}


def _wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("조건을 기다리다 시간 초과")
        time.sleep(0.01)


@pytest.fixture
def fake_be(monkeypatch):
    """실제 ai/.env·DB 없이 lifespan을 띄우고, 콜백은 가짜 BE로 받는다."""
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    for name in ("DATABASE_URL", "MODEL_PROFILE_OVERRIDES", "AI_DEV_API_ENABLED", "AI_DEV_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    for cached in (config.get_settings, database.get_engine, database.get_session_factory):
        cached.cache_clear()

    received: list[httpx.Request] = []
    lock = threading.Lock()

    def handler(request):
        with lock:
            received.append(request)
        return httpx.Response(200, json={"code": "OK", "message": "", "data": None})

    monkeypatch.setattr(main, "HttpCallbackSender", lambda base_url, token: HttpCallbackSender(
        base_url, token, transport=httpx.MockTransport(handler)))
    yield received
    for cached in (config.get_settings, database.get_engine, database.get_session_factory):
        cached.cache_clear()


def test_접수한_상품의_진행과_결과가_BE_콜백으로_나간다(fake_be):
    with TestClient(main.app) as client:
        response = client.post("/api/ai/v1/diagnose/content", json={
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
    assert len(result["assessment"]["toolReviews"]) == 6


def test_개발용_진단은_상태_조회로_결과를_보고_BE로는_콜백을_보내지_않는다(fake_be, monkeypatch):
    key = "test-dev-api-key-0123456789abcdefgh"
    monkeypatch.setenv("AI_DEV_API_ENABLED", "true")
    monkeypatch.setenv("AI_DEV_API_KEY", key)
    headers = {"X-Dev-Api-Key": key}

    with TestClient(main.app) as client:
        accepted = client.post("/api/ai/v1/dev/diagnose", json={"textBlocks": ["상품 설명"]}, headers=headers)
        product_id = accepted.json()["data"]["productId"]

        def status():
            return client.get(f"/api/ai/v1/dev/diagnose/{product_id}", headers=headers).json()["data"]

        _wait_until(lambda: status()["status"] == "completed")
        done = status()

    assert accepted.status_code == 202
    assert done["assessment"]["status"] == "completed"
    assert done["result"] is not None
    assert fake_be == []


def test_지표_경로가_세션_현황과_끝난_세션을_보여준다(fake_be):
    with TestClient(main.app) as client:
        client.post("/api/ai/v1/diagnose/content", json={
            "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}],
        })
        _wait_until(lambda: 'ai_session_finished_total{outcome="completed",run_type="production"} 1.0'
                    in client.get("/metrics").text)
        text = client.get("/metrics").text

    assert 'ai_sessions{status="completed"} 1.0' in text
    assert 'ai_session_accepted_total{run_type="production"} 1.0' in text


def test_서버가_떠_있는_동안만_에이전트_호출이_지표에_쌓인다(fake_be):
    meta = AgentRunMeta(component="extraction", model="m", elapsed_ms=100)
    sample = {"component": "extraction", "model": "m", "outcome": "ok"}

    with TestClient(main.app) as client:
        agent_sinks.publish(meta, "p-1")
        registry = main.app.state.metrics_registry
        text = client.get("/metrics").text
    agent_sinks.publish(meta, "p-2")

    assert 'ai_agent_calls_total{component="extraction",model="m",outcome="ok"} 1.0' in text
    # 종료 때 해제돼 이후 호출은 옛 registry에 쌓이지 않음
    assert registry.get_sample_value("ai_agent_calls_total", sample) == 1.0
