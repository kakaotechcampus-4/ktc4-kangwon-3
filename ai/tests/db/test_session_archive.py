"""진단 세션 보관 객체를 DB 없이 검증한다. Repository를 dict로 흉내 냄."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.db import session_archive
from app.db.fetchers import DbSkip
from app.db.session_archive import SessionArchiveDatabase
from app.domain.context import ExecutionContext, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.session import DiagnosisSession, SessionAnswer, SessionStatus

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class _Db:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        _Db.commits += 1


@pytest.fixture
def rows(monkeypatch):
    """Repository를 상품 ID → 행 dict로 바꾼다."""
    stored = {}

    class _Repository:
        def __init__(self, db):
            pass

        def put(self, record):
            stored[record.product_id] = record

        def delete(self, product_ids):
            return sum(stored.pop(product_id, None) is not None for product_id in product_ids)

        def load_all(self):
            return sorted(stored.values(), key=lambda record: record.updated_at)

    _Db.commits = 0
    monkeypatch.setattr(session_archive, "DiagnosisSessionRepository", _Repository)
    return stored


def _awaiting(product_id: str = "p-1") -> DiagnosisSession:
    """복원에 필요한 칸(원래 입력·질문·답변·이전 결과)을 다 채운 답변 대기 세션."""
    return DiagnosisSession(
        context=ExecutionContext.start(product_id=product_id, run_type=RunType.PRODUCTION, diagnosis_id="d-1"),
        source=ExtractionInput(product_id=product_id, text_blocks=["상품 설명"], image_urls=["https://img/1.jpg"]),
        status=SessionStatus.AWAITING_INPUT,
        result=build_dummy_assessment(product_id),
        question_round=1,
        questions=[PublicQuestionDto(question_key="voltage", question_order=1, question_text="정격 전압은?")],
        answers=[SessionAnswer(question_round=1, question_key="voltage", answer_text="5V")],
        accepted_at=NOW, updated_at=NOW,
    )


def test_저장한_세션을_읽으면_그대로_돌아온다(rows):
    archive = SessionArchiveDatabase(_Db)
    session = _awaiting()

    archive.save(session)

    record = rows["p-1"]
    assert (record.status, record.run_type, record.updated_at) == ("awaiting_input", "production", NOW)
    assert archive.load() == [session]
    assert _Db.commits == 1


def test_지우면_다시_읽을_때_빠진다(rows):
    archive = SessionArchiveDatabase(_Db)
    archive.save(_awaiting("p-1"))
    archive.save(_awaiting("p-2"))

    archive.remove(["p-1"])

    assert [session.context.product_id for session in archive.load()] == ["p-2"]


def test_지금_세션_모양과_안_맞는_행은_경고_후_지운다(rows, caplog):
    archive = SessionArchiveDatabase(_Db)
    archive.save(_awaiting("p-1"))
    archive.save(_awaiting("p-2"))
    rows["p-1"].session = {"status": "unknown"}

    loaded = archive.load()

    assert [session.context.product_id for session in loaded] == ["p-2"]
    assert "p-1" not in rows
    assert "보관된 진단 세션을 읽지 못해 지움 (product_id=p-1)" in caplog.text


def test_DB_실패는_경고만_남기고_일정_시간_DB를_건너뛴다(rows, caplog):
    calls = []

    def broken_factory():
        calls.append(1)
        raise OperationalError("SELECT 1", {}, Exception("연결 실패"))

    clock = [0.0]
    archive = SessionArchiveDatabase(broken_factory, skip=DbSkip(monotonic=lambda: clock[0]))

    archive.save(_awaiting())
    archive.remove(["p-1"])

    assert len(calls) == 1
    assert "진단 세션 DB 저장 실패" in caplog.text
    assert archive.load() == []


def test_지울_상품이_없으면_DB를_부르지_않는다(rows):
    calls = []
    SessionArchiveDatabase(lambda: calls.append(1)).remove([])

    assert calls == []
