"""기동 때 만드는 부품. 운영 부품(production_parts)과 테스트가 가짜를 넣는 묶음(AppParts)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from ..agents.input_guard import InputGuardAgent
from ..clients.backend import BackendCallbackClient
from ..clients.llm.embedding import embed_texts_sync
from ..config import SESSION_DRAIN_SECONDS, SESSION_SWEEP_SECONDS, Settings
from ..diagnosis import build_job, build_parts, build_questions, guarded
from ..dummy import run_case_diagnosis
from ..db import (CUSTOMS_GW_CACHE, DatabaseNotConfiguredError, SessionArchiveDatabase, build_law_fetchers,
                  get_session_factory, init_db, log_law_changes, purge_expired_responses, refresh_laws, run_law_refresh,
                  run_scheduled_clip_ingest, run_weekly_clip_ingest)
from ..sessions.job import DiagnosisJob
from ..sessions.manager import SessionManager
from ..sessions.store import SessionArchive, SessionStore
from ..tools.common.law_sources import LAW_SOURCES, applied_version

logger = logging.getLogger(__name__)


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
    # DB 연결 확인·vector 확장·테이블 생성 (있으면 건너뜀)
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
        # 운영·샌드박스 진단 함수 (에이전트·Tool 한 번 생성해 공용, 실행 첫머리 입력 가드)
        pipeline_job=guarded(build_job(build_parts(), build_questions), InputGuardAgent().run),
        dummy_job=run_case_diagnosis,
        # BE 콜백 전송 (#317)
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
        # 재시작 때 되살릴 세션 보관소 (#565)
        archive=SessionArchiveDatabase(session_factory),
        # 예약 작업: 법령 점검(매일, 기동 때는 안 돎. 시행예정 포함 본문), CLIP 결정사례 적재(매주 새 사례)
        background=(lambda: run_law_refresh(daily_refresh), lambda: run_weekly_clip_ingest(clip_ingest)),
        # 법령 조회 연결 닫기 (실행 중 점검은 끝까지 돌고 닫힌 연결 오류는 그 문서 실패로 남음)
        close=law_fetchers.close,
    )
