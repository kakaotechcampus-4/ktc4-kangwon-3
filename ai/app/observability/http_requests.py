"""AI 서버가 받은 HTTP 요청을 측정 기록(HttpRequest)으로 남기는 미들웨어."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from .measurements import HttpRequest, measurement_sinks

# Prometheus 수집 요청. 수집 주기마다 쌓여 실제 요청 수치를 가림
SKIPPED_PATHS = frozenset({"/metrics"})
# 맞는 라우트가 없는 요청(404 등). 원래 경로를 라벨로 쓰면 아무 경로나 시계열이 됨
UNMATCHED_ROUTE = "unmatched"


async def record_http_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """요청 1건의 라우트 템플릿·메서드·상태 코드·처리 시간을 남긴다.

    Args:
        request: 받은 요청.
        call_next: 다음 처리 단계.

    Returns:
        Response: 다음 처리 단계의 응답 그대로.

    Raises:
        Exception: 처리 중 예외. 500으로 남기고 그대로 올림 (공통 예외 처리기가 응답을 만듦).
    """
    if request.url.path in SKIPPED_PATHS:
        return await call_next(request)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # 라우팅이 끝나야 scope에 route가 들어옴
        route = request.scope.get("route")
        measurement_sinks.publish(HttpRequest(
            route=getattr(route, "path", UNMATCHED_ROUTE), method=request.method, status=status,
            seconds=time.perf_counter() - started,
        ))
