"""AI 전용 PostgreSQL(pgvector) 엔진·세션 관리.

설정 값(DATABASE_URL)은 config/settings.py가 읽고 검증하고, 이 모듈은 그 값으로 DB 자원만 만든다.
import만으로는 DB에 접근하지 않는다. 엔진은 처음 필요할 때 만들어 프로세스 전체가 공유한다.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from ..config import ConfigError, get_settings
from .errors import DatabaseNotConfiguredError


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """공통 설정의 DATABASE_URL로 SQLAlchemy 엔진을 만들어 돌려준다.

    처음 호출할 때 한 번 만들고 이후에는 같은 엔진을 돌려준다.
    엔진을 만드는 것만으로는 DB에 연결하지 않는다.

    Returns:
        Engine: 커넥션 풀을 가진 공용 엔진.

    Raises:
        DatabaseNotConfiguredError: DATABASE_URL이 비어 있는 경우.
        ConfigError: 접속 문자열을 해석할 수 없거나 DB 드라이버가 없는 경우.
    """
    database_url = get_settings().database_url
    if not database_url:
        raise DatabaseNotConfiguredError("DATABASE_URL이 설정되지 않아 DB 기능을 사용할 수 없습니다.")
    try:
        return create_engine(
            database_url,
            pool_size=5,
            max_overflow=5,
            # DB에 패킷이 닿지 않으면 OS TCP 타임아웃(약 2분)까지 기다리므로 제한한다.
            connect_args={
                "connect_timeout": 3,
                # HNSW 기본 탐색 폭(40)에선 거리가 비슷한 1·2위가 뒤바뀜 (#247)
                "options": "-c hnsw.ef_search=100",
            },
        )
    except (ArgumentError, ImportError) as e:
        # URL 형식이나 드라이버 문제는 기다려도 풀리지 않는 설정·배포 오류다.
        # 접속 문자열에는 DB 비밀번호가 들어 있어 원본 메시지 대신 예외 타입만 남긴다.
        raise ConfigError(f"DATABASE_URL로 DB 엔진을 만들 수 없습니다 ({type(e).__name__}).") from e


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """공용 엔진에 묶인 세션 팩토리를 돌려준다.

    Returns:
        sessionmaker[Session]: 세션을 만드는 팩토리.

    Raises:
        DatabaseNotConfiguredError: DATABASE_URL이 비어 있는 경우.
        ConfigError: 엔진을 만들 수 없는 경우.
    """
    return sessionmaker(bind=get_engine())


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 의존성 주입용 DB 세션 제너레이터.

    Yields:
        Session: SQLAlchemy DB 세션. 요청 종료 시 자동으로 닫힌다.
    """
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db() -> list[str]:
    """vector 확장과 ORM 모델 테이블을 만든다. 이미 있는 확장·테이블은 건너뛴다.

    Returns:
        list[str]: 새로 만든 테이블 이름.

    Raises:
        DatabaseNotConfiguredError: DATABASE_URL이 비어 있는 경우.
        ConfigError: 엔진을 만들 수 없는 경우.
        sqlalchemy.exc.OperationalError: DB에 연결할 수 없는 경우.
    """
    from app.models import Base

    with get_engine().begin() as conn:
        # docker-entrypoint-initdb.d는 볼륨을 처음 만들 때만 돎
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        existing = set(inspect(conn).get_table_names())
        Base.metadata.create_all(bind=conn)
    return [table.name for table in Base.metadata.sorted_tables if table.name not in existing]

