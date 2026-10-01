"""BaseRepository 공통 CRUD를 DB 없이 검증한다. 트랜잭션(commit)은 호출부 책임."""

from app.models import Law
from app.repositories.base import BaseRepository


def _law(law_id: int | None = None) -> Law:
    return Law(law_id=law_id, law_mst="273575", law_code="008044", name_ko="전안법 시행규칙", law_type="부령", is_current=True)


def test_create는_추가_후_flush만_하고_commit하지_않는다(session):
    entity = _law()

    result = BaseRepository(session, Law).create(entity)

    assert result is entity
    assert session.added == [entity]
    assert session.flushed == 1


def test_create_many는_한_번에_추가하고_한_번_flush한다(session):
    entities = [_law(), _law()]

    BaseRepository(session, Law).create_many(entities)

    assert session.added == entities
    assert session.flushed == 1


def test_get_all은_offset과_limit으로_페이징한다(session):
    BaseRepository(session, Law).get_all(offset=20, limit=10)

    sql = session.last_sql()
    assert "LIMIT %(param_1)s OFFSET %(param_2)s" in sql
    assert session.statements[-1].compile().params == {"param_1": 10, "param_2": 20}


def test_update는_있는_엔티티의_필드만_바꾼다(session):
    session.stored[1] = _law(law_id=1)

    updated = BaseRepository(session, Law).update(1, is_current=False)

    assert updated.is_current is False
    assert session.flushed == 1


def test_update와_delete는_없는_ID면_아무것도_하지_않는다(session):
    repo = BaseRepository(session, Law)

    assert repo.update(999, is_current=False) is None
    assert repo.delete(999) is False
    assert session.deleted == []
    assert session.flushed == 0


def test_delete는_있는_엔티티를_지우고_True를_돌려준다(session):
    entity = _law(law_id=1)
    session.stored[1] = entity

    assert BaseRepository(session, Law).delete(1) is True
    assert session.deleted == [entity]
