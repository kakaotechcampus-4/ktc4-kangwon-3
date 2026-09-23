"""AI 전용 PostgreSQL(pgvector) 연결 설정.

config.py는 LLM(ChatOpenAI) 설정 전용이므로 DB 연결은 여기서 관리한다.
DATABASE_URL은 docker-compose.yml 또는 .env에서 주입한다.
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from dotenv import load_dotenv

# .env 파일 경로 설정 및 환경 변수 로드
_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_ENV_FILE, override=False)

# DATABASE_URL 환경 변수를 가져오고 검증하기
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL이 없습니다. {_ENV_FILE}에 DB 연결 문자열을 설정하세요.")

# SQLAlchemy 엔진 및 세션 설정
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine)

def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 의존성 주입용 DB 세션 제너레이터.

    Yields:
        Session: SQLAlchemy DB 세션. 요청 종료 시 자동으로 닫힌다.
    """
    db = SessionLocal()
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

    Base.metadata.create_all(bind=engine)


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

    with engine.begin() as conn:
        for name, table, ops, lists in _VECTOR_INDEXES:
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} "
                f"ON {table} USING ivfflat ({ops}) "
                f"WITH (lists = {lists})"
            ))
