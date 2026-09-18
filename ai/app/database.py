"""AI 전용 PostgreSQL(pgvector) 연결 설정.

config.py는 LLM(ChatOpenAI) 설정 전용이므로 DB 연결은 여기서 관리한다.
DATABASE_URL은 docker-compose.yml 또는 .env에서 주입한다.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from dotenv import load_dotenv

_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_ENV_FILE, override=False)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL이 없습니다. {_ENV_FILE}에 DB 연결 문자열을 설정하세요.")

engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=5)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속할 베이스 클래스."""
    pass


def get_db():
    """FastAPI 의존성 주입용 DB 세션 제너레이터."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
