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
    """
    from app.models import Base

    Base.metadata.create_all(bind=engine)
