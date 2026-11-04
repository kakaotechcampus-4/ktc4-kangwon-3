"""AI 전용 DB(PostgreSQL + pgvector)와 그 위의 조회 객체.

바깥(Tool·스케줄러·main)은 이 모듈이 내보내는 것만 쓴다. models·repositories는 app/db 안에서만 쓴다.

    - fetchers: 외부 API 응답을 DB에서 먼저 찾는 조회 객체 (Tool이 클라이언트 자리에 넣음)
    - law_cache: 법제처 조회 객체 묶음과 법령 점검 스케줄러 / law_changes: 점검이 찾은 법령 변경
    - customs_cache: 관세청 세관장확인대상물품 GW 조회 객체
    - clip_cases: CLIP 결정사례 DB 조회 객체 / clip_ingest: 그 적재 (cli clip-ingest)
    - engine: 엔진·세션·테이블 생성
    - models / repositories: 테이블과 DB 입출력 (내부용)
    - cli: python -m app.db.cli
"""

from .clip_cases import ClipCaseDatabase
from .clip_ingest import run_scheduled_clip_ingest, run_weekly_clip_ingest
from .customs_cache import CUSTOMS_GW_CACHE, build_customs_gw_fetcher, open_customs_gw_fetcher
from .engine import get_session_factory, init_db
from .errors import DatabaseNotConfiguredError
from .fetchers import (
    SHARED_DB_SKIP, CachedFetcherBase, DbSkip, OnDemandFetcher, ScheduledFetcher, purge_expired_responses,
)
from .law_cache import (
    LawFetchers, LawRefreshReport, build_law_fetchers, open_law_fetchers, refresh_laws, run_law_refresh,
)
from .law_changes import LawChange, LawChangeKind, LawChangeSink, LawVersion, log_law_changes

__all__ = [
    "CUSTOMS_GW_CACHE",
    "SHARED_DB_SKIP",
    "CachedFetcherBase",
    "ClipCaseDatabase",
    "DatabaseNotConfiguredError",
    "DbSkip",
    "LawChange",
    "LawChangeKind",
    "LawChangeSink",
    "LawFetchers",
    "LawRefreshReport",
    "LawVersion",
    "OnDemandFetcher",
    "ScheduledFetcher",
    "build_customs_gw_fetcher",
    "build_law_fetchers",
    "get_session_factory",
    "init_db",
    "log_law_changes",
    "open_customs_gw_fetcher",
    "open_law_fetchers",
    "purge_expired_responses",
    "refresh_laws",
    "run_scheduled_clip_ingest",
    "run_law_refresh",
    "run_weekly_clip_ingest",
]
