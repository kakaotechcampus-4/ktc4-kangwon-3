"""create_app이 만든 앱에 라우터·인증·요청 지표·기본 부품 함수가 연결되는지 확인한다.

기동·종료 연결은 tests/startup/test_lifespan.py, 운영 부품은 tests/startup/test_parts.py.
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.app_harness import FakeBackend, app_env, client, fake_parts

pytestmark = pytest.mark.integration

PRODUCT = {"diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["상품 설명"]}]}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    yield from app_env(monkeypatch)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


def test_운영_경로는_내부_토큰이_없으면_401이고_접수하지_않는다(backend):
    with client(fake_parts(backend)) as app:
        response = app.post("/api/ai/v1/diagnose/content", json=PRODUCT)
        session = app.app.state.session_manager.get("p-1")

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert session is None
    assert backend.requests == []


def test_더미_경로는_내부_토큰이_없으면_401이고_접수하지_않는다(backend):
    # 형식이 틀린 요청도 422보다 401이 먼저 (토큰 없이 요청 형식을 떠보지 못하게)
    path = "/api/ai/v1/dummy/diagnose/content"
    with client(fake_parts(backend)) as app:
        response = app.post(path, json=PRODUCT)
        malformed = app.post(path, json={"diagnosisId": "d-1"})
        session = app.app.state.session_manager.get("p-1")

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert malformed.status_code == 401
    assert session is None
    assert backend.requests == []


def test_지표_경로에_받은_HTTP_요청이_라우트_템플릿으로_나온다(backend):
    with client(fake_parts(backend)) as app:
        app.get("/api/ai/v1/health")
        text = app.get("/metrics").text

    assert 'ai_http_requests_total{method="GET",route="/api/ai/v1/health",status="200"} 1.0' in text
    assert 'route="/metrics"' not in text


def test_부품_함수를_넘기지_않으면_운영_부품으로_기동한다(backend, monkeypatch):
    called = []
    monkeypatch.setattr(main, "production_parts", lambda settings: called.append(settings) or fake_parts(backend))

    with TestClient(main.create_app()) as app:
        response = app.get("/api/ai/v1/health")

    assert response.status_code == 200
    assert len(called) == 1
