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

# Counter·Histogram마다 붙는 _created(처음 만든 시각) 시계열을 내보내지 않음. Prometheus는 재시작을 _total 감소로 알아챔
disable_created_metrics()

# 종료 시 남은 콜백을 보내는 최대 대기 시간. 넘으면 버리고 로그만 남김
# 콜백 요청 하나의 대기 상한(5초)에 재시도 두어 번이 들어가게 둠
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
            # 구독자(콜백 전송) 호출이 동기라 이벤트 루프 밖에서 실행
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

    Args:
        app: 띄울 앱.
        build_parts: 설정으로 기동 부품을 만드는 함수.
    """
    settings = get_settings()
    # 이후 기동 로그부터 설정한 레벨로 (설정 전엔 WARNING 이상만)
    configure_logging(settings.log_level)
    logger.info("환경변수 검증 완료 (로그 레벨 %s)", settings.log_level)
    # 이후 ERROR 로그·잡지 않은 예외가 Sentry로 감
    configure_sentry(settings.sentry_dsn, settings.sentry_environment, settings.sentry_log_level)

    parts = build_parts(settings)
    database = parts.database
    background = [] if database is None else [asyncio.create_task(run()) for run in database.background]

    # 공개 진단서 변환기 (#405). 콜백·샌드박스 상태 조회가 같이 씀
    presenter = ResultPresenter()
    # 운영·샌드박스는 실제 파이프라인, BE 연동용(/dummy)은 케이스 더미
    job = by_run_type({
        RunType.PRODUCTION: parts.pipeline_job,
        RunType.TEST: parts.pipeline_job,
        RunType.DUMMY: parts.dummy_job,
    })
    # DB 없으면 메모리에만 둠 (재시작 때 사라짐)
    archive = None if database is None else database.archive
    manager = parts.session_manager(SessionStore(archive=archive), job)
    outbox = CallbackOutbox(parts.callback_sender)
    connect_callbacks(manager, EventBuilder(presenter), outbox)
    with app_metrics(manager, outbox) as registry:
        app.state.metrics_registry = registry
        app.state.session_manager = manager
        # 콜백·지표 구독 뒤 복원 (되살린 세션 결과도 콜백으로)
        if archive is not None:
            manager.restore(await asyncio.to_thread(archive.load))
        app.state.assessment_presenter = presenter
        sweeper = asyncio.create_task(_sweep_sessions(manager, parts.sweep_seconds))
        try:
            yield
        finally:
            for task in background:
                await _cancel(task)
            if database is not None:
                database.close()
            # 실행 중 세션은 상한까지 기다림, 대기열 세션은 취소(콜백 없음)
            # 상한 넘긴 스레드는 uvicorn 종료 뒤 SIGTERM으로 끊김. BE는 멈춤 감지(15분)로 실패 처리
            await asyncio.to_thread(manager.drain, parts.drain_seconds)
            # 정리 루프는 drain 뒤 멈춤 (기다리는 중 시간 초과 세션도 실패 콜백)
            await _cancel(sweeper)
            # 세션 관리자 멈춘 뒤 남은 콜백 전송. 못 보낸 이벤트는 발신함이 로그
            await asyncio.to_thread(outbox.close, CALLBACK_CLOSE_SECONDS)
            parts.callback_sender.close()
            # 상한 넘긴 스레드의 남은 모델 호출은 실패 (결과 콜백은 이미 버려짐)
            close_llm_clients()
            close_decision_clients()
