"""진단 세션 보관 Repository가 만드는 SQL을 DB 없이 검증한다."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.db.models import DiagnosisSessionRecord
from app.db.repositories.diagnosis_session import DiagnosisSessionRepository


def _record(**overrides) -> DiagnosisSessionRecord:
    fields = {
        "product_id": "p-1", "status": "accepted", "run_type": "production",
        "updated_at": datetime(2026, 11, 4, tzinfo=timezone.utc), "session": {"status": "accepted"},
    }
    return DiagnosisSessionRecord(**{**fields, **overrides})


def test_저장은_같은_상품이면_상태와_세션을_덮어쓴다(session):
    DiagnosisSessionRepository(session).put(_record())

    sql = session.last_sql()
    assert sql.startswith("INSERT INTO diagnosis_sessions")
    assert "ON CONFLICT (product_id) DO UPDATE SET" in sql
    for column in ("status", "run_type", "updated_at", "session"):
        assert f"{column} = excluded.{column}" in sql
    assert "fetched_at = now()" in sql
    assert "product_id = excluded.product_id" not in sql


def test_삭제는_주어진_상품만_지우고_지운_수를_돌려준다(session):
    session.execute = lambda stmt: session.statements.append(stmt) or SimpleNamespace(rowcount=2)

    deleted = DiagnosisSessionRepository(session).delete(["p-1", "p-2"])

    assert deleted == 2
    assert "DELETE FROM diagnosis_sessions WHERE diagnosis_sessions.product_id IN" in session.last_sql()
    assert session.statements[-1].compile().params["product_id_1"] == ["p-1", "p-2"]


def test_지울_상품이_없으면_DB를_부르지_않는다(session):
    assert DiagnosisSessionRepository(session).delete([]) == 0
    assert session.statements == []


def test_전체_읽기는_오래_바뀌지_않은_순으로_가져온다(session):
    DiagnosisSessionRepository(session).load_all()

    sql = session.last_sql()
    assert sql.startswith("SELECT diagnosis_sessions.")
    assert sql.endswith("ORDER BY diagnosis_sessions.updated_at")
