"""Repository 테스트 공통 가짜 세션. 실행되는 SQL을 가로채 PostgreSQL 문법으로 확인한다."""

from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql


class RecordingSession:
    """Repository가 쓰는 Session 메서드만 흉내 내고 호출 내역을 남긴다."""

    def __init__(self):
        self.statements = []
        self.added = []
        self.deleted = []
        self.flushed = 0
        self.stored: dict = {}

    def scalars(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(first=lambda: None, all=lambda: [])

    def execute(self, stmt):
        self.statements.append(stmt)
        return iter([])

    def get(self, model, entity_id):
        return self.stored.get(entity_id)

    def add(self, entity):
        self.added.append(entity)

    def add_all(self, entities):
        self.added.extend(entities)

    def delete(self, entity):
        self.deleted.append(entity)

    def flush(self):
        self.flushed += 1

    def last_sql(self) -> str:
        return str(self.statements[-1].compile(dialect=postgresql.dialect()))


@pytest.fixture
def session() -> RecordingSession:
    return RecordingSession()
