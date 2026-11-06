"""FastAPI 앱 엔트리포인트."""

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from .config import Settings
from .observability.http_requests import record_http_requests
from .routers import diagnose, dummy, health, metrics, sandbox
from .routers.exception_handlers import VALIDATION_ERROR_RESPONSES, register_exception_handlers
from .startup.lifespan import lifespan as _lifespan
from .startup.parts import AppParts, production_parts


def create_app(build_parts: Callable[[Settings], AppParts] | None = None) -> FastAPI:
    """앱을 만든다. 부품은 기동(lifespan 시작) 때 만들어 import만으로는 외부 연결이 생기지 않음.

    Args:
        build_parts: 설정으로 기동 부품을 만드는 함수. None이면 운영 부품(production_parts).
            테스트는 가짜 부품을 돌려주는 함수를 넣음.

    Returns:
        FastAPI: 라우터·예외 처리·요청 지표를 붙인 앱.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 기동 부품 생성 함수 선택 (기본: 운영 부품)
        async with _lifespan(app, build_parts or production_parts):
            yield

    app = FastAPI(
        title="팔기전에 AI",
        description="해외 수입품 국내 판매 규제 진단 API",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    # HTTP 요청 지표 (라우트 템플릿 기준)
    app.middleware("http")(record_http_requests)

    api_v1 = APIRouter(prefix="/api/ai/v1")
    api_v1.include_router(health.router)
    # 운영·더미 진단 접수 (Swagger 422를 공통 응답 형식으로 표시)
    api_v1.include_router(diagnose.router, responses=VALIDATION_ERROR_RESPONSES)
    api_v1.include_router(dummy.router, responses=VALIDATION_ERROR_RESPONSES)
    # 샌드박스 진단 (#318, 외부 공개, 꺼지면 404·키 없으면 401)
    api_v1.include_router(sandbox.router, responses=VALIDATION_ERROR_RESPONSES)

    app.include_router(api_v1)
    # Prometheus 수집 경로 (BE /actuator/prometheus 대응, /api/ai/ 밖)
    app.include_router(metrics.router)
    return app


# uvicorn 진입점 (app.main:app)
app = create_app()
