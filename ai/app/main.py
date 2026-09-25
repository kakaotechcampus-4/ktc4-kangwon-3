"""FastAPI 앱 엔트리포인트."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from .config import load_settings
from .database import engine
from .routers import diagnose, dummy, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 필수 설정과 외부 연결을 검증한다.

    검증 실패 시 예외가 전파되어 서버가 뜨지 않는다.
    """
    load_settings()
    logger.info("LLM 설정 검증 완료")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("DB 연결 확인 완료")
    except Exception as e:
        logger.warning("DB 연결 실패 — DB 의존 기능은 동작하지 않습니다: %s", e)

    yield


app = FastAPI(
    title="팔기전에 AI",
    description="해외 수입품 국내 판매 규제 진단 API",
    version="0.1.0",
    lifespan=lifespan,
)

api_v1 = APIRouter(prefix="/api/ai/v1")
api_v1.include_router(health.router)
api_v1.include_router(diagnose.router)
api_v1.include_router(dummy.router)

app.include_router(api_v1)
