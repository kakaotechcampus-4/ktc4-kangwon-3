"""Prometheus 지표 엔드포인트를 서버 기동(lifespan) 없이 검증한다."""

from fastapi.testclient import TestClient

from app.main import app


def test_metrics는_prometheus_형식으로_응답한다():
    response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE process_resident_memory_bytes gauge" in response.text


def test_metrics는_api_경로_밖에_있다():
    # nginx는 /api/ai/만 AI로 넘김
    client = TestClient(app)

    assert client.get("/api/ai/v1/metrics").status_code == 404


def test_metrics는_openapi_문서에_노출되지_않는다():
    assert "/metrics" not in app.openapi()["paths"]
