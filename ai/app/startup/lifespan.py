"""서버 기동·종료 순서. 부품을 받아 세션 관리자·콜백·지표를 잇고, 종료 때 역순으로 닫음."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, disable_created_metrics

from ..callbacks import CallbackOutbox, EventBuilder, connect_callbacks
from ..clients.llm import close_llm_clients
from ..clients.llm.decision import close_decision_clients
from ..config import Settings, get_settings
from ..domain.context import RunType
from ..observability.agent_sinks import agent_sinks
from ..observability.logs import configure_logging
from ..observability.measurements import measurement_sinks
from ..observability.metrics import (
    AgentMetrics, CallbackOutboxCollector, MeasurementMetrics, SessionMetrics, SessionSnapshotCollector,
)
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


@asynccontextmanager
async def lifespan(app: FastAPI, build_parts: Callable[[Settings], AppParts]):
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
