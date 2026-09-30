"""Prometheus 지표 수집과 노출 설정.

지표 정의(무엇을 셀지)는 metrics.py, 여기는 앱에 수집을 걸고 전용 포트로 내보내는 일만 한다.
"""

from wsgiref.simple_server import WSGIServer

from fastapi import FastAPI
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# 앱 포트(8000) + 1, compose에서 미공개 (BE 8080 / actuator 8081과 동일 구조)
METRICS_PORT = 8001

# 진단 요청은 수십 초 소요 (기본 구간은 1초까지)
HTTP_LATENCY_BUCKETS = (0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120)


def instrument_http(app: FastAPI) -> None:
    """앱의 HTTP 요청 수와 응답시간을 수집하도록 설정한다.

    라우트 템플릿·메서드·상태코드별로 집계하고 health 요청은 제외한다.
    노출은 start_metrics_server()가 띄우는 전용 서버가 담당한다.

    Args:
        app: 수집을 걸 FastAPI 앱.
    """
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/api/ai/v1/health.*"],
    ).add(
        metrics.default(latency_lowr_buckets=HTTP_LATENCY_BUCKETS, latency_highr_buckets=HTTP_LATENCY_BUCKETS),
    ).instrument(app)


def start_metrics_server(port: int = METRICS_PORT) -> WSGIServer:
    """Prometheus 지표 전용 HTTP 서버를 별도 스레드로 띄운다.

    진단 요청이 앱 이벤트 루프를 붙잡아도 지표 응답은 끊기지 않는다.

    Args:
        port: 지표 서버 포트. 0이면 빈 포트를 자동으로 고른다.

    Returns:
        WSGIServer: 종료 시 shutdown()을 호출할 서버.

    Raises:
        OSError: 포트를 이미 사용 중인 경우.
    """
    server, _ = start_http_server(port)
    return server
