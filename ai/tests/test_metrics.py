"""Prometheus 지표 수집과 지표 전용 서버를 앱 기동(lifespan) 없이 검증한다."""

import httpx
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from app.main import app
from app.monitoring import start_metrics_server


def _exposed() -> str:
    return generate_latest(REGISTRY).decode()


def test_지표_서버는_별도_포트에서_prometheus_형식으로_응답한다():
    server = start_metrics_server(port=0)
    try:
        response = httpx.get(f"http://127.0.0.1:{server.server_port}/metrics")
    finally:
        server.shutdown()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE process_resident_memory_bytes gauge" in response.text


def test_앱_포트에는_metrics_경로가_없다():
    # 지표는 전용 포트에서만 노출
    client = TestClient(app)

    assert client.get("/metrics").status_code == 404
    assert client.get("/api/ai/v1/metrics").status_code == 404


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


def test_health_요청은_집계하지_않는다():
    TestClient(app).get("/api/ai/v1/health")

    assert 'handler="/api/ai/v1/health"' not in _exposed()


def test_응답시간_구간은_120초까지_있다():
    TestClient(app).post(DUMMY_ROUTE, json={})

    assert f'http_request_duration_seconds_bucket{{handler="{DUMMY_ROUTE}",le="120.0",method="POST"}}' in _exposed()
