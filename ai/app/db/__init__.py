"""AI 전용 DB(PostgreSQL + pgvector)와 그 위의 조회 객체.

바깥(Tool·스케줄러·main)은 이 모듈이 내보내는 것만 쓴다. models·repositories는 app/db 안에서만 쓴다.

    - fetchers: 외부 API 응답을 DB에서 먼저 찾는 조회 객체 (Tool이 클라이언트 자리에 넣음)
    - engine: 엔진·세션·테이블 생성
    - models / repositories: 테이블과 DB 입출력 (내부용)
    - cli: python -m app.db.cli
"""

from .engine import get_session_factory, init_db
from .errors import DatabaseNotConfiguredError
from .fetchers import CachedFetcherBase, OnDemandFetcher, ScheduledFetcher

__all__ = [
    "CachedFetcherBase",
    "DatabaseNotConfiguredError",
    "OnDemandFetcher",
    "ScheduledFetcher",
    "get_session_factory",
    "init_db",
]
