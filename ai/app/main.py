"""FastAPI 앱 엔트리포인트."""

from fastapi import FastAPI

from .routers import diagnose, dummy, health

app = FastAPI(
    title="팔기전에 AI",
    description="해외 수입품 국내 판매 규제 진단 API",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(diagnose.router)
app.include_router(dummy.router)
