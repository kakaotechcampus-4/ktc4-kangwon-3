"""Recall 모델의 고유 제약을 DB 없이 검증한다."""

from sqlalchemy import UniqueConstraint

from app.models import Recall


def _unique_column_sets() -> list[set[str]]:
    table = Recall.__table__
    sets = [
        {column.name for column in constraint.columns}
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    sets += [{column.name} for column in table.columns if column.unique]
    return sets


def test_리콜은_출처와_원본_ID_조합으로_고유하다():
    # 국내·국외 리콜 ID 2,047건 중복 (#209)
    assert {"source", "source_uid"} in _unique_column_sets()


def test_원본_ID_단독으로는_고유_제약이_없다():
    assert {"source_uid"} not in _unique_column_sets()
