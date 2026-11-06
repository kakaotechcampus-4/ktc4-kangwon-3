"""서버 기동·종료 순서. 부품을 받아 세션 관리자·콜백·지표를 잇고, 종료 때 역순으로 닫음."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from prometheus_client import disable_created_metrics

from ..callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from ..clients.llm import close_llm_clients
from ..clients.llm.decision import close_decision_clients
from ..config import Settings, get_settings
from ..domain.context import RunType
from ..observability.logs import configure_logging
from ..observability.metrics import app_metrics
from ..observability.sentry import configure_sentry
from ..results.presenter import ResultPresenter
from ..sessions.job import by_run_type
from ..sessions.manager import SessionManager
from ..sessions.store import SessionStore
from .parts import AppParts

logger = logging.getLogger(__name__)

# Counter·Histogram의 _created(처음 만든 시각) 시계열 끄기
disable_created_metrics()

# 종료 때 남은 콜백 전송 대기 상한(초). 요청 상한 5초 + 재시도 두어 번
CALLBACK_CLOSE_SECONDS = 15.0


async def _sweep_sessions(manager: SessionManager, interval: float) -> None:
    """시간 초과 세션 실패 처리와 보관 시간 지난 세션 삭제를 주기적으로 실행한다.

    Args:
        manager: 정리할 세션 관리자.
        interval: 정리 주기(초).
    """
    while True:
        await asyncio.sleep(interval)
        try:
            # 시간 초과 세션 실패 처리·보관 만료 세션 삭제 (스레드에서)
            await asyncio.to_thread(manager.expire_overdue)
            await asyncio.to_thread(manager.purge)
        except Exception:
            logger.exception("세션 정리 실패")


async def _cancel(task: asyncio.Task) -> None:
    """작업을 취소하고 끝날 때까지 기다린다.

    Args:
        task: 취소할 작업.
    """
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@asynccontextmanager
async def lifespan(app: FastAPI, build_parts: Callable[[Settings], AppParts]):
    """기동 때 설정을 검증하고 부품을 이어 진단 세션 관리자를 띄운다. 종료 때 역순으로 닫는다.

    설정·부품 생성 오류는 잡지 않고 전파해 서버가 뜨지 않게 함.
    세션 복원은 콜백·지표 연결 뒤 (되살린 세션의 결과도 콜백으로 나가게).
    종료 때 상한을 넘긴 실행 중 세션은 버림 (스레드는 uvicorn 종료 뒤 SIGTERM으로 끊기고, BE는 멈춤 감지 15분으로 실패 처리).

    Args:
        app: 띄울 앱.
        build_parts: 설정으로 기동 부품을 만드는 함수.
    """
    settings = get_settings()
    # 로그 레벨 설정
    configure_logging(settings.log_level)
    logger.info("환경변수 검증 완료 (로그 레벨 %s)", settings.log_level)
    # Sentry 오류·로그 전송 설정
    configure_sentry(settings.sentry_dsn, settings.sentry_environment, settings.sentry_log_level)

    # 기동 부품 생성·예약 작업 시작
    parts = build_parts(settings)
    database = parts.database
    background = [] if database is None else [asyncio.create_task(run()) for run in database.background]

    # 공개 진단서 변환기 (#405, 콜백·샌드박스 상태 조회 공용)
    presenter = ResultPresenter()
    # 실행 종류별 진단 함수 (운영·샌드박스: 실제 파이프라인, /dummy: 케이스 더미)
    job = by_run_type({
        RunType.PRODUCTION: parts.pipeline_job,
        RunType.TEST: parts.pipeline_job,
        RunType.DUMMY: parts.dummy_job,
    })
    # 세션 관리자 (DB 없으면 메모리 보관)
    archive = None if database is None else database.archive
    manager = parts.session_manager(SessionStore(archive=archive), job)
    # BE 콜백 발신함·세션 이벤트 연결
    outbox = CallbackOutbox(parts.callback_sender)
    connect_callbacks(manager, EventBuilder(presenter), outbox)
    # 지표 연결 (블록을 나가면 공용 sink 해제)
    with app_metrics(manager, outbox) as registry:
        app.state.metrics_registry = registry
        app.state.session_manager = manager
        # 재시작 전 세션 복원
        if archive is not None:
            manager.restore(await asyncio.to_thread(archive.load))
        app.state.assessment_presenter = presenter
        # 시간 초과·보관 만료 세션 정리 루프
        sweeper = asyncio.create_task(_sweep_sessions(manager, parts.sweep_seconds))
        try:
            yield
        finally:
            # 예약 작업 취소·DB 부품 정리
            for task in background:
                await _cancel(task)
            if database is not None:
                database.close()
            # 실행 중 세션 대기 (상한 drain_seconds), 대기열 세션 취소
            await asyncio.to_thread(manager.drain, parts.drain_seconds)
            # 세션 정리 루프 중지 (drain 중 시간 초과 세션까지 처리한 뒤)
            await _cancel(sweeper)
            # 남은 콜백 전송·BE 전송 닫기
            await asyncio.to_thread(outbox.close, CALLBACK_CLOSE_SECONDS)
            parts.callback_sender.close()
            # 모델 클라이언트 닫기
            close_llm_clients()
            close_decision_clients()
