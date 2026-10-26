"""지표 라우터: /metrics가 registry를 Prometheus 텍스트로 내보내는지 확인한다."""

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter

from app.main import app
from app.routers.metrics import get_metrics_registry


@pytest.fixture
def client():
    registry = CollectorRegistry()
    Counter("ai_example", "예시 지표", registry=registry).inc(3)
    app.dependency_overrides[get_metrics_registry] = lambda: registry
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_지표를_Prometheus_텍스트로_반환한다(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "ai_example_total 3.0" in response.text


def test_외부_공개_경로와_Swagger에는_없다(client):
    assert client.get("/api/ai/v1/metrics").status_code == 404
    assert "/metrics" not in app.openapi()["paths"]
