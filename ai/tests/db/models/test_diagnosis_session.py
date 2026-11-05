"""진단 세션 보관 모델의 제약을 DB 없이 검증한다."""

from app.db.models import DiagnosisSessionRecord


def test_세션은_상품_ID_하나로_찾는다():
    assert [column.name for column in DiagnosisSessionRecord.__table__.primary_key] == ["product_id"]


def test_복원에_쓰는_칸은_비워_둘_수_없다():
    columns = DiagnosisSessionRecord.__table__.c
    assert [name for name in ("status", "run_type", "updated_at", "session") if columns[name].nullable] == []


def test_변경_시각은_시간대를_담는다():
    assert DiagnosisSessionRecord.__table__.c.updated_at.type.timezone is True
