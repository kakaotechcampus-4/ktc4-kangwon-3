"""FastAPI 앱 엔트리포인트."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI
from prometheus_client import CollectorRegistry, disable_created_metrics
from sqlalchemy.exc import SQLAlchemyError

from .agents.input_guard import InputGuardAgent
from .callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from .clients.backend import BackendCallbackClient
from .clients.llm import close_llm_clients
from .clients.llm.decision import close_decision_clients
from .clients.llm.embedding import embed_texts_sync
from .config import SESSION_DRAIN_SECONDS, SESSION_SWEEP_SECONDS, Settings, get_settings
from .diagnosis import build_job, build_parts, build_questions, guarded
from .domain.context import RunType
from .dummy import run_case_diagnosis
from .observability.agent_sinks import agent_sinks
from .observability.http_requests import record_http_requests
from .observability.logs import configure_logging
from .observability.measurements import measurement_sinks
from .observability.metrics import (
    AgentMetrics, CallbackOutboxCollector, MeasurementMetrics, SessionMetrics, SessionSnapshotCollector,
)
from .observability.sentry import configure_sentry
from .db import (CUSTOMS_GW_CACHE, DatabaseNotConfiguredError, SessionArchiveDatabase, build_law_fetchers,
                 get_session_factory, init_db, log_law_changes, purge_expired_responses, refresh_laws, run_law_refresh,
                 run_scheduled_clip_ingest, run_weekly_clip_ingest)
from .routers import diagnose, dummy, health, metrics, sandbox
from .results.presenter import ResultPresenter
from .routers.exception_handlers import VALIDATION_ERROR_RESPONSES, register_exception_handlers
from .sessions.job import DiagnosisJob, by_run_type
from .sessions.manager import SessionManager
from .sessions.store import SessionArchive, SessionStore
from .tools.common.law_sources import LAW_SOURCES, applied_version

logger = logging.getLogger(__name__)

# Counter·Histogram마다 붙는 _created(처음 만든 시각) 시계열을 내보내지 않음. Prometheus는 재시작을 _total 감소로 알아챔
disable_created_metrics()

# 종료 시 남은 콜백을 보내는 최대 대기 시간. 넘으면 버리고 로그만 남김
# 콜백 요청 하나의 대기 상한(5초)에 재시도 두어 번이 들어가게 둠
CALLBACK_CLOSE_SECONDS = 15.0


@dataclass(frozen=True)
class AppDatabase:
    """DB가 준비됐을 때만 붙는 기동 부품.

    Attributes:
        archive: 재시작 때 되살릴 세션 보관소.
        background: 기동 뒤 돌릴 예약 작업 (법령 점검·결정사례 적재). 종료 때 취소.
        close: 예약 작업을 멈춘 뒤 부르는 정리 (법령 조회 연결 닫기).
    """

    archive: SessionArchive
    background: tuple[Callable[[], Awaitable[None]], ...]
    close: Callable[[], None]


@dataclass(frozen=True)
class AppParts:
    """기동 때 만드는 부품. 운영은 production_parts, 테스트는 가짜를 넣어 외부 연결 없이 앱을 띄움.

    Attributes:
        pipeline_job: 운영·샌드박스 진단 함수 (입력 가드 포함).
        dummy_job: BE 연동 확인용 더미 진단 함수.
        callback_sender: BE 콜백 전송. 종료 때 닫음.
        database: DB 부품. None이면 세션은 메모리에만 두고 예약 작업 없음.
        session_manager: 세션 저장소·진단 함수로 세션 관리자를 만드는 함수.
        sweep_seconds: 시간 초과·보관 만료 세션 정리 주기(초).
        drain_seconds: 종료 때 실행 중 세션을 기다리는 상한(초).
    """

    pipeline_job: DiagnosisJob
    dummy_job: DiagnosisJob
    callback_sender: BackendCallbackClient
    database: AppDatabase | None
    session_manager: Callable[[SessionStore, DiagnosisJob], SessionManager]
    sweep_seconds: float
    drain_seconds: float


def production_parts(settings: Settings) -> AppParts:
    """운영 부품을 만든다. 기동 때 한 번 부름.

    설정을 고쳐야 하는 문제(엔진 생성 실패·모델 설정 오류 등 ConfigError)는 그대로 터져 기동을 막는다.
    개발 단계에서 의도적으로 비워둔 DATABASE_URL과, 아직 뜨지 않은 DB는 경고만 남긴다.

    Args:
        settings: 검증된 환경 설정.

    Returns:
        AppParts: 실제 DB·파이프라인·BE 콜백 전송.

    Raises:
        ConfigError: 모델·키·DB 설정이 잘못된 경우.
    """
    database = None
    # 연결 확인 겸 vector 확장·테이블 생성 (이미 있으면 건너뜀)
    try:
        created = init_db()
    except DatabaseNotConfiguredError:
        logger.warning("DATABASE_URL 미설정 — DB 기능 없이 기동합니다")
    except SQLAlchemyError as e:
        logger.warning("DB 준비 실패 — DB 의존 기능은 동작하지 않습니다: %s", e)
    else:
        logger.info("DB 준비 완료 (새로 만든 테이블: %s)", ", ".join(created) or "없음")
        database = _production_database(settings)
    return AppParts(
        # 에이전트·Tool은 여기서 한 번 만들어 모든 진단이 같이 씀
        # 입력 가드는 접수 뒤 실행 첫머리에서 (차단은 늦춘 일반 실패)
        pipeline_job=guarded(build_job(build_parts(), build_questions), InputGuardAgent().run),
        dummy_job=run_case_diagnosis,
        # BE 콜백 (#317)
        callback_sender=BackendCallbackClient(settings.be_base_url, settings.internal_api_token),
        database=database,
        session_manager=SessionManager,
        sweep_seconds=SESSION_SWEEP_SECONDS,
        drain_seconds=SESSION_DRAIN_SECONDS,
    )


def _production_database(settings: Settings) -> AppDatabase:
    """DB가 준비됐을 때 세션 보관소와 예약 작업을 만든다.

    Args:
        settings: 검증된 환경 설정.

    Returns:
        AppDatabase: 세션 보관소, 법령 점검·결정사례 적재 예약 작업, 정리 함수.
    """
    session_factory = get_session_factory()
    law_fetchers = build_law_fetchers(settings.law_oc, session_factory, measure=False)

    def daily_refresh() -> None:
        refresh_laws(law_fetchers, LAW_SOURCES, select=applied_version, on_change=log_law_changes)
        purge_expired_responses(session_factory, [CUSTOMS_GW_CACHE])

    def clip_ingest():
        return run_scheduled_clip_ingest(session_factory, embed=lambda texts: embed_texts_sync(texts, settings),
                                         embedding_model=settings.embedding_model)

    return AppDatabase(
        # 재시작 때 되살릴 세션은 DB에 같이 보관 (#565)
        archive=SessionArchiveDatabase(session_factory),
        # 법령 점검: 기동 30초 뒤 1번, 이후 매일. 근거 문서 본문(시행예정 포함)을 미리 DB에 받아 둠
        # CLIP 결정사례: 매주 새 사례만 적재
        background=(lambda: run_law_refresh(daily_refresh), lambda: run_weekly_clip_ingest(clip_ingest)),
        # 실행 중인 점검 스레드는 끝까지 돎. 닫힌 클라이언트 오류는 그 문서 실패로만 남음
        close=law_fetchers.close,
    )


async def _sweep_sessions(manager: SessionManager, interval: float) -> None:
    """시간 초과 세션 실패 처리와 보관 시간 지난 세션 삭제를 주기적으로 실행한다.

    Args:
        manager: 정리할 세션 관리자.
        interval: 정리 주기(초).
    """
    while True:
        await asyncio.sleep(interval)
        try:
            # 구독자(콜백 전송) 호출이 동기라 이벤트 루프 밖에서 실행
            await asyncio.to_thread(manager.expire_overdue)
            await asyncio.to_thread(manager.purge)
        except Exception:
            logger.exception("세션 정리 실패")


@asynccontextmanager
async def _lifespan(app: FastAPI, build_parts: Callable[[Settings], AppParts]):
    """서버 기동 시 필수 설정과 외부 연결을 검증하고 진단 세션 관리자를 띄운다.

    검증 실패 시 예외가 전파되어 서버가 뜨지 않는다. 종료 시 정리 작업과 세션 관리자를 닫는다.

    Args:
        app: 띄울 앱.
        build_parts: 설정으로 기동 부품을 만드는 함수.
    """

    ## 에러가 발생하면 서버가 뜨지 않도록, try-except로 잡지 않고 그대로 전파한다.
    settings = get_settings()
    # 설정이 없으면 app 로그가 WARNING 이상만 나옴. 이후 기동 로그부터 이 레벨로
    configure_logging(settings.log_level)
    logger.info("환경변수 검증 완료 (로그 레벨 %s)", settings.log_level)
    # 오류 전송. 이후 기동·진단 중 ERROR 로그와 요청 처리 중 잡지 않은 예외가 감
    configure_sentry(settings.sentry_dsn, settings.sentry_environment, settings.sentry_log_level)

    parts = build_parts(settings)
    database = parts.database
    background = [] if database is None else [asyncio.create_task(run()) for run in database.background]

    # 공개 진단서 변환기 (#405). 콜백과 샌드박스 상태 조회가 같이 씀
    presenter = ResultPresenter()
    # 진단 세션 (#264). 운영(/diagnose)·샌드박스는 실제 파이프라인 ([콜백 5/5]), BE 연동용(/dummy)은 케이스 더미
    job = by_run_type({
        RunType.PRODUCTION: parts.pipeline_job,
        RunType.TEST: parts.pipeline_job,
        RunType.DUMMY: parts.dummy_job,
    })
    # DB가 없으면 메모리에만 둬 재시작 때 사라짐
    archive = None if database is None else database.archive
    manager = parts.session_manager(SessionStore(archive=archive), job)
    sender = parts.callback_sender
    outbox = CallbackOutbox(sender)
    connect_callbacks(manager, EventBuilder(presenter), outbox)
    # 세션 지표. 앱마다 registry를 따로 둬 테스트에서 lifespan을 여러 번 띄워도 이름이 겹치지 않음
    registry = CollectorRegistry()
    manager.subscribe(SessionMetrics(registry).on_event)
    registry.register(SessionSnapshotCollector(manager))
    registry.register(CallbackOutboxCollector(outbox))
    # 에이전트 지표. 등록표는 앱 전체 공용이라 종료 때 해제 (lifespan을 다시 띄워도 옛 registry에 안 쌓이게)
    agent_metrics = AgentMetrics(registry).on_run
    agent_sinks.add(agent_metrics)
    # 외부 API·콜백·Tool·추출 측정 지표. 에이전트 지표와 같은 이유로 종료 때 해제
    measurement_metrics = MeasurementMetrics(registry).on_record
    measurement_sinks.add(measurement_metrics)
    app.state.metrics_registry = registry
    app.state.session_manager = manager
    # 콜백·지표 구독을 다 붙인 뒤 되살림 (복원한 세션의 결과도 콜백으로 나가게)
    if archive is not None:
        manager.restore(await asyncio.to_thread(archive.load))
    # 샌드박스 진단 상태 조회도 콜백과 같은 변환기로 공개 진단서를 만듦
    app.state.assessment_presenter = presenter
    sweeper = asyncio.create_task(_sweep_sessions(manager, parts.sweep_seconds))
    try:
        yield
    finally:
        for task in background:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if database is not None:
            database.close()
        # 실행 중 세션은 상한 시간까지 기다림(끝난 결과는 콜백으로). 대기열 세션은 취소됨(콜백 없음)
        # 상한을 넘긴 실행 중 스레드는 uvicorn이 종료 처리 뒤 SIGTERM을 다시 발생시켜 함께 끊김.
        # 버리는 세션은 관리자가 경고로 남김. BE는 멈춤 감지(15분)로 실패 처리
        await asyncio.to_thread(manager.drain, parts.drain_seconds)
        # 정리 루프는 drain 뒤에 멈춤. 기다리는 중 최대 시간을 넘긴 세션도 시간 초과 실패 콜백으로 끝냄
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        # 세션 관리자를 먼저 멈춘 뒤 남은 콜백을 보냄. 시간 안에 못 보낸 이벤트는 발신함이 로그로 남김
        await asyncio.to_thread(outbox.close, CALLBACK_CLOSE_SECONDS)
        sender.close()
        # 상한을 넘긴 실행 중 스레드의 남은 모델 호출은 실패함. 결과 콜백은 이미 버려지는 상태라 영향 없음
        close_llm_clients()
        close_decision_clients()
        agent_sinks.remove(agent_metrics)
        measurement_sinks.remove(measurement_metrics)


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
        # 기동 때 찾음 (운영 부품 함수를 테스트에서 바꿔치기해도 반영)
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
    # 요청 본문이 있는 라우터만 Swagger 422를 공통 응답 형식으로 표시. health는 422가 나지 않음
    api_v1.include_router(diagnose.router, responses=VALIDATION_ERROR_RESPONSES)
    api_v1.include_router(dummy.router, responses=VALIDATION_ERROR_RESPONSES)
    # 샌드박스 진단 (#318). 외부에 여는 경로, 꺼져 있으면 404·키 없으면 401
    api_v1.include_router(sandbox.router, responses=VALIDATION_ERROR_RESPONSES)

    app.include_router(api_v1)
    # Prometheus 수집 경로 (BE /actuator/prometheus 대응). 외부 공개 경로(/api/ai/) 밖에 둠
    app.include_router(metrics.router)
    return app


# uvicorn app.main:app
app = create_app()
