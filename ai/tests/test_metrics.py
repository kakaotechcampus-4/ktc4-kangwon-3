"""Prometheus 지표 엔드포인트를 서버 기동(lifespan) 없이 검증한다."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

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


def _requests_total(handler: str, method: str, status: str) -> float:
    value = REGISTRY.get_sample_value(
        "http_requests_total", {"handler": handler, "method": method, "status": status}
    )
    return value or 0.0


DUMMY_ROUTE = "/api/ai/v1/dummy/diagnose/content"


def test_요청은_라우트_템플릿과_상태코드별로_집계된다():
    # 빈 본문은 검증 실패(422), 상태코드는 2xx·4xx로 묶지 않음
    before = _requests_total(DUMMY_ROUTE, "POST", "422")

    TestClient(app).post(DUMMY_ROUTE, json={})

    assert _requests_total(DUMMY_ROUTE, "POST", "422") == before + 1


def test_없는_경로는_하나의_handler로_묶인다():
    # 임의 경로마다 라벨이 늘어나지 않도록 함
    before = _requests_total("none", "GET", "404")

    TestClient(app).get("/api/ai/v1/unknown-path-for-metrics-test")

    assert _requests_total("none", "GET", "404") == before + 1


def test_health와_metrics_요청은_집계하지_않는다():
    client = TestClient(app)
    client.get("/api/ai/v1/health")
    client.get("/metrics")

    body = client.get("/metrics").text
    assert 'handler="/api/ai/v1/health"' not in body
    assert 'handler="/metrics"' not in body


def test_응답시간_구간은_120초까지_있다():
    client = TestClient(app)
    client.post(DUMMY_ROUTE, json={})

    body = client.get("/metrics").text
    assert f'http_request_duration_seconds_bucket{{handler="{DUMMY_ROUTE}",le="120.0",method="POST"}}' in body
