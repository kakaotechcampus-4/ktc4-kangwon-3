"""FastAPI 앱 엔트리포인트."""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .database import DatabaseNotConfiguredError, get_engine
from .routers import diagnose, dummy, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 필수 설정과 외부 연결을 검증한다.

    검증 실패 시 예외가 전파되어 서버가 뜨지 않는다.
    """

    ## 에러가 발생하면 서버가 뜨지 않도록, try-except로 잡지 않고 그대로 전파한다.
    get_settings()
    logger.info("환경변수 검증 완료")

    # 설정을 고쳐야 하는 문제(엔진 생성 실패 등 ConfigError)는 여기서 그대로 터져 기동을 막는다.
    # 개발 단계에서 의도적으로 비워둔 DATABASE_URL과, 아직 뜨지 않은 DB는 경고만 남긴다.
    try:
        engine = get_engine()
    except DatabaseNotConfiguredError:
        logger.warning("DATABASE_URL 미설정 — DB 기능 없이 기동합니다")
    else:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("DB 연결 확인 완료")
        except SQLAlchemyError as e:
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

# /api/ai/v1 밖에 둠 (nginx가 /api/ai/만 프록시하므로 외부 미노출)
Instrumentator().expose(app, endpoint="/metrics", include_in_schema=False)
