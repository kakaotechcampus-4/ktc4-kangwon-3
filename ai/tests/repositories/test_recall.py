"""RecallRepository의 조회·upsert SQL을 DB 없이 검증한다."""

from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.recall import RecallRepository


class _RecordingSession:
    def __init__(self):
        self.statements = []

    def execute(self, stmt):
        self.statements.append(stmt)
        params = stmt.compile(dialect=postgresql.dialect()).params
        returned = [key for key in params if key.startswith("source_uid")]
        return SimpleNamespace(all=lambda: returned)

    def flush(self):
        pass


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _row(source: str, source_uid: str, product_name: str = "제품") -> dict:
    return {"source": source, "source_uid": source_uid, "product_name": product_name}


def test_upsert는_출처와_원본_ID_기준으로_충돌을_처리한다():
    session = _RecordingSession()

    RecallRepository(session).upsert_many([_row("domestic", "10018912"), _row("foreign", "10018912")])

    sql = _sql(session.statements[0])
    assert "ON CONFLICT (source, source_uid) DO UPDATE" in sql
    assert "product_name = excluded.product_name" in sql
    assert "fetched_at = now()" in sql


def test_upsert는_넘기지_않은_embedding을_갱신하지_않는다():
    # 재적재 시 기존 임베딩 유지
    session = _RecordingSession()

    RecallRepository(session).upsert_many([_row("domestic", "10018912")])

    set_clause = _sql(session.statements[0]).split("DO UPDATE SET", 1)[1]
    assert "embedding" not in set_clause


def test_upsert는_같은_키가_여러_번_있으면_마지막_값만_보낸다():
    session = _RecordingSession()

    RecallRepository(session).upsert_many([
        _row("domestic", "10018912", "베이스볼캡"),
        _row("domestic", "10018912", "베이스볼캡(수정)"),
        _row("foreign", "10018912", "딸랑이완구"),
    ])

    params = session.statements[0].compile(dialect=postgresql.dialect()).params
    names = sorted(v for k, v in params.items() if k.startswith("product_name"))
    assert names == ["딸랑이완구", "베이스볼캡(수정)"]


def test_upsert는_batch_size_단위로_나눠_보낸다():
    session = _RecordingSession()
    rows = [_row("foreign", str(i)) for i in range(2500)]

    affected = RecallRepository(session).upsert_many(rows, batch_size=1000)

    assert len(session.statements) == 3
    assert affected == 2500


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        # 첫 행에만 embedding: 뒷행 값이 없어 SQL 생성 실패하던 경우
        (
            [{**_row("domestic", "1"), "embedding": [0.1]}, _row("domestic", "2")],
            r"rows\[1\].*빠진 키: \['embedding'\]",
        ),
        # 뒷행에만 embedding: 갱신 대상에서 빠져 조용히 버려지던 경우
        (
            [_row("domestic", "1"), {**_row("foreign", "2"), "embedding": [0.1]}],
            r"rows\[1\].*추가된 키: \['embedding'\]",
        ),
    ],
)
def test_upsert는_행마다_키가_다르면_보내기_전에_거부한다(rows, message):
    session = _RecordingSession()

    with pytest.raises(ValueError, match=message):
        RecallRepository(session).upsert_many(rows)

    assert session.statements == []


def test_upsert는_빈_목록이면_아무것도_보내지_않는다():
    session = _RecordingSession()

    assert RecallRepository(session).upsert_many([]) == 0
    assert session.statements == []


def test_출처와_원본_ID로_조회한다():
    captured = []
    session = SimpleNamespace(scalars=lambda stmt: captured.append(stmt) or SimpleNamespace(first=lambda: None))

    RecallRepository(session).get_by_source_uid("foreign", "10018912")

    sql = _sql(captured[0])
    assert "recalls.source = %(source_1)s" in sql
    assert "recalls.source_uid = %(source_uid_1)s" in sql
