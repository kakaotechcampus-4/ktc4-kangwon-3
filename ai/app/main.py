"""FastAPI 앱 엔트리포인트."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from prometheus_client import CollectorRegistry
from sqlalchemy.exc import SQLAlchemyError

from .callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from .clients.backend import BackendCallbackClient
from .clients.llm import close_llm_clients
from .config import SESSION_SWEEP_SECONDS, get_settings
from .observability.agent_sinks import agent_sinks
from .observability.metrics import AgentMetrics, SessionMetrics, SessionSnapshotCollector
from .db import (CUSTOMS_GW_CACHE, DatabaseNotConfiguredError, build_law_fetchers, get_session_factory, init_db,
                 log_law_changes, purge_expired_responses, refresh_laws, run_law_refresh)
from .routers import dev_diagnose, diagnose, dummy, health, metrics
from .routers._dummy import DummyAssessmentPresenter, run_dummy_diagnosis
from .routers.exception_handlers import VALIDATION_ERROR_RESPONSES, register_exception_handlers
from .sessions.manager import SessionManager
from .sessions.store import SessionStore
from .tools.common.law_sources import LAW_SOURCES, applied_version

logger = logging.getLogger(__name__)

# 종료 시 남은 콜백을 보내는 최대 대기 시간. 넘으면 버리고 로그만 남김
CALLBACK_CLOSE_SECONDS = 5.0


async def _sweep_sessions(manager: SessionManager) -> None:
    """시간 초과 세션 실패 처리와 보관 시간 지난 세션 삭제를 주기적으로 실행한다.

    Args:
        manager: 정리할 세션 관리자.
    """
    while True:
        await asyncio.sleep(SESSION_SWEEP_SECONDS)
        try:
            # 구독자(콜백 전송) 호출이 동기라 이벤트 루프 밖에서 실행
            await asyncio.to_thread(manager.expire_overdue)
            await asyncio.to_thread(manager.purge)
        except Exception:
            logger.exception("세션 정리 실패")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 필수 설정과 외부 연결을 검증하고 진단 세션 관리자를 띄운다.

    검증 실패 시 예외가 전파되어 서버가 뜨지 않는다. 종료 시 정리 작업과 세션 관리자를 닫는다.
    """

    ## 에러가 발생하면 서버가 뜨지 않도록, try-except로 잡지 않고 그대로 전파한다.
    settings = get_settings()
    logger.info("환경변수 검증 완료")

    # 설정을 고쳐야 하는 문제(엔진 생성 실패 등 ConfigError)는 여기서 그대로 터져 기동을 막는다.
    # 개발 단계에서 의도적으로 비워둔 DATABASE_URL과, 아직 뜨지 않은 DB는 경고만 남긴다.
    # 연결 확인 겸 vector 확장·테이블 생성 (이미 있으면 건너뜀)
    law_fetchers = session_factory = None
    try:
        created = init_db()
    except DatabaseNotConfiguredError:
        logger.warning("DATABASE_URL 미설정 — DB 기능 없이 기동합니다")
    except SQLAlchemyError as e:
        logger.warning("DB 준비 실패 — DB 의존 기능은 동작하지 않습니다: %s", e)
    else:
        logger.info("DB 준비 완료 (새로 만든 테이블: %s)", ", ".join(created) or "없음")
        # 법령 점검: 기동 직후 1번, 이후 매일. 근거 문서 본문(시행예정 포함)을 미리 DB에 받아 둠
        session_factory = get_session_factory()
        law_fetchers = build_law_fetchers(settings.law_oc, session_factory)

    def daily_refresh() -> None:
        refresh_laws(law_fetchers, LAW_SOURCES, select=applied_version, on_change=log_law_changes)
        purge_expired_responses(session_factory, [CUSTOMS_GW_CACHE])

    law_refresher = None if law_fetchers is None else asyncio.create_task(run_law_refresh(daily_refresh))

    # 실제 진단서·질문 변환기([콜백 5/5]) 전까지 가짜 진단용 변환기
    presenter = DummyAssessmentPresenter()
    # 진단 세션 (#264). 파이프라인 러너 연결 전까지 더미 진단으로 실행
    manager = SessionManager(SessionStore(), run_dummy_diagnosis)
    # BE 콜백 (#317)
    sender = BackendCallbackClient(settings.be_base_url, settings.internal_api_token)
    outbox = CallbackOutbox(sender)
    connect_callbacks(manager, EventBuilder(presenter), outbox)
    # 세션 지표. 앱마다 registry를 따로 둬 테스트에서 lifespan을 여러 번 띄워도 이름이 겹치지 않음
    registry = CollectorRegistry()
    manager.subscribe(SessionMetrics(registry).on_event)
    registry.register(SessionSnapshotCollector(manager))
    # 에이전트 지표. 등록표는 앱 전체 공용이라 종료 때 해제 (lifespan을 다시 띄워도 옛 registry에 안 쌓이게)
    agent_metrics = AgentMetrics(registry).on_run
    agent_sinks.add(agent_metrics)
    app.state.metrics_registry = registry
    app.state.session_manager = manager
    # 개발용 진단 상태 조회도 콜백과 같은 변환기로 공개 진단서를 만듦
    app.state.assessment_presenter = presenter
    sweeper = asyncio.create_task(_sweep_sessions(manager))
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        if law_refresher is not None:
            # 실행 중인 점검 스레드는 끝까지 돎. 닫힌 클라이언트 오류는 그 문서 실패로만 남음
            law_refresher.cancel()
            with suppress(asyncio.CancelledError):
                await law_refresher
            law_fetchers.close()
        # 대기열 세션은 취소됨(콜백 없음). 실행 중 스레드는 프로세스 종료 때 끝까지 돌지만
        # 발신함이 먼저 닫혀 이후 콜백은 버려짐. BE는 멈춤 감지(15분)로 실패 처리
        manager.shutdown(wait=False)
        # 세션 관리자를 먼저 멈춘 뒤 남은 콜백을 보냄. 시간 안에 못 보낸 이벤트는 발신함이 로그로 남김
        await asyncio.to_thread(outbox.close, CALLBACK_CLOSE_SECONDS)
        sender.close()
        # 실행 중 스레드의 남은 모델 호출은 실패함. 결과 콜백은 이미 버려지는 상태라 영향 없음
        close_llm_clients()
        agent_sinks.remove(agent_metrics)


app = FastAPI(
    title="팔기전에 AI",
    description="해외 수입품 국내 판매 규제 진단 API",
    version="0.1.0",
    lifespan=lifespan,
)
register_exception_handlers(app)

api_v1 = APIRouter(prefix="/api/ai/v1")
api_v1.include_router(health.router)
# 요청 본문이 있는 라우터만 Swagger 422를 공통 응답 형식으로 표시. health는 422가 나지 않음
api_v1.include_router(diagnose.router, responses=VALIDATION_ERROR_RESPONSES)
api_v1.include_router(dummy.router, responses=VALIDATION_ERROR_RESPONSES)
# 개발용 진단 (#318). 외부에 여는 경로, 꺼져 있으면 404·키 없으면 401
api_v1.include_router(dev_diagnose.router, responses=VALIDATION_ERROR_RESPONSES)

app.include_router(api_v1)
# Prometheus 수집 경로 (BE /actuator/prometheus 대응). 외부 공개 경로(/api/ai/) 밖에 둠
app.include_router(metrics.router)
