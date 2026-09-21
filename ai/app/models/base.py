from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속할 베이스 클래스."""
    pass
