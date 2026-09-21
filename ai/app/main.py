"""FastAPI 앱 엔트리포인트."""

from fastapi import APIRouter, FastAPI

from .routers import diagnose, dummy, health

app = FastAPI(
    title="팔기전에 AI",
    description="해외 수입품 국내 판매 규제 진단 API",
    version="0.1.0",
)

api_v1 = APIRouter(prefix="/api/ai/v1")
api_v1.include_router(health.router)
api_v1.include_router(diagnose.router)
api_v1.include_router(dummy.router)

app.include_router(api_v1)
