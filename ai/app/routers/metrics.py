"""Prometheus 수집용 지표 라우터. /api/ai/v1 밖(/metrics)에 두고 Swagger에는 싣지 않음."""

from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest

router = APIRouter(tags=["지표"])


def get_metrics_registry(request: Request) -> CollectorRegistry:
    """lifespan에서 만든 지표 registry를 꺼낸다. 테스트에서 의존성 교체용."""
    return request.app.state.metrics_registry


@router.get("/metrics", include_in_schema=False)
async def metrics(registry: CollectorRegistry = Depends(get_metrics_registry)) -> Response:
    """지표를 Prometheus 텍스트 형식으로 반환한다.

    Args:
        registry: 지표 registry.

    Returns:
        Prometheus 텍스트 형식 응답.
    """
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
