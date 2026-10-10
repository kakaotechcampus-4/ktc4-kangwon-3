"""FastAPI 앱 엔트리포인트."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import SESSION_SWEEP_SECONDS, get_settings
from .database import DatabaseNotConfiguredError, get_engine
from .routers import diagnose, dummy, health
from .routers._dummy import run_dummy_diagnosis
from .sessions.executor import SessionExecutor
from .sessions.store import SessionStore

logger = logging.getLogger(__name__)


async def _sweep_sessions(executor: SessionExecutor) -> None:
    """시간 초과 세션 실패 처리와 보관 시간 지난 세션 삭제를 주기적으로 실행한다.

    Args:
        executor: 정리할 세션 실행기.
    """
    while True:
        await asyncio.sleep(SESSION_SWEEP_SECONDS)
        try:
            # 구독자(콜백 전송) 호출이 동기라 이벤트 루프 밖에서 실행
            await asyncio.to_thread(executor.expire_overdue)
            await asyncio.to_thread(executor.store.purge)
        except Exception:
            logger.exception("세션 정리 실패")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 필수 설정과 외부 연결을 검증하고 진단 세션 실행기를 띄운다.

    검증 실패 시 예외가 전파되어 서버가 뜨지 않는다. 종료 시 정리 작업과 실행기를 닫는다.
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

    # 진단 세션 (#264). 파이프라인 러너 연결 전까지 더미 진단으로 실행
    executor = SessionExecutor(SessionStore(), run_dummy_diagnosis)
    app.state.session_executor = executor
    sweeper = asyncio.create_task(_sweep_sessions(executor))
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        # 메모리 세션이라 재시작 시 어차피 사라짐. 실행 중 세션은 기다리지 않음
        executor.shutdown(wait=False)


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
