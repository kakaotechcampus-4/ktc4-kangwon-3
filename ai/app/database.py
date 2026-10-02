"""AI 전용 PostgreSQL(pgvector) 엔진·세션 관리.

설정 값(DATABASE_URL)은 config.py가 읽고 검증하고, 이 모듈은 그 값으로 DB 자원만 만든다.
import만으로는 DB에 접근하지 않는다. 엔진은 처음 필요할 때 만들어 프로세스 전체가 공유한다.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from .config import ConfigError, get_settings


class DatabaseNotConfiguredError(ConfigError):
    """DATABASE_URL이 비어 있어 DB를 쓸 수 없다.

    개발 단계에서는 DB 없이도 서버를 띄울 수 있게 의도적으로 허용하는 상태라,
    설정이 틀린 경우(ConfigError)와 구분해서 기동 시 경고만 남긴다.
    """


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
            connect_args={"connect_timeout": 3},
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


def init_db() -> None:
    """ORM 모델 기반 테이블 생성.

    Base.metadata에 등록된 모든 ORM 모델의 테이블을 생성한다.
    이미 존재하는 테이블은 건너뛴다.
    IVFFlat 벡터 인덱스는 여기서 생성하지 않는다. 빈 테이블에
    IVFFlat을 만들면 클러스터 중심점이 없어 검색이 동작하지 않으므로,
    데이터 적재 후 create_vector_indexes()를 호출해야 한다.
    """
    from app.models import Base

    Base.metadata.create_all(bind=get_engine())


_VECTOR_INDEXES = [
    (
        "ix_law_articles_embedding",
        "law_articles",
        "embedding vector_cosine_ops",
        100,
    ),
    (
        "ix_hs_cases_embedding",
        "hs_cases",
        "embedding vector_cosine_ops",
        50,
    ),
    (
        "ix_recalls_embedding",
        "recalls",
        "embedding vector_cosine_ops",
        50,
    ),
]


def create_vector_indexes() -> None:
    """IVFFlat 벡터 인덱스를 생성한다. 데이터 적재 후 호출한다.

    이미 존재하는 인덱스는 건너뛴다.
    데이터 분포가 크게 바뀌면 기존 인덱스를 DROP 후 다시 호출한다.
    """
    from sqlalchemy import text

    with get_engine().begin() as conn:
        for name, table, ops, lists in _VECTOR_INDEXES:
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} "
                f"ON {table} USING ivfflat ({ops}) "
                f"WITH (lists = {lists})"
            ))
