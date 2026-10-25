"""CLIP 결정사례 DB 조회 객체를 DB·임베딩 없이 검증한다."""

import pytest

from app.db import clip_cases
from app.db.clip_cases import ClipCaseDatabase
from app.db.models.hs_case import HsCase
from app.schemas.clients.customs_response import CLIPCase


def _row(doc_id: str, hs_codes: list[str]) -> HsCase:
    return HsCase(doc_id=doc_id, hs_codes=hs_codes, product_name=f"품명{doc_id}", description="설명",
                  decision_reason="사유", enforce_date="20240101", embedding=[0.1] * 1536, embedding_model="m")


class _Session:
    closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        _Session.closed = True
        return False


@pytest.fixture
def repo(monkeypatch):
    """HsCaseRepository를 가짜로 바꾸고 받은 인자를 기록한다."""
    calls = {}

    class _Repository:
        def __init__(self, session):
            pass

        def search_by_vector(self, vector, *, embedding_model, top_k):
            calls["vector"] = (vector, embedding_model, top_k)
            return [(_row("1", ["8516310000"]), 0.12), (_row("2", ["851631"]), 0.3)]

        def get_by_hs_code(self, hs_code):
            calls["hs_code"] = hs_code
            return [_row("1", ["8516310000"])]

    _Session.closed = False
    monkeypatch.setattr(clip_cases, "HsCaseRepository", _Repository)
    return calls


def _database(embedded: list[str]) -> ClipCaseDatabase:
    return ClipCaseDatabase(_Session, embed_query=lambda text: embedded.append(text) or [0.2] * 1536,
                            embedding_model="openai/text-embedding-3-small")


def test_비슷한_사례는_글을_임베딩해_같은_모델_벡터로_찾고_클라이언트와_같은_모양으로_돌려준다(repo):
    embedded = []

    results = _database(embedded).search_similar("전기 헤어드라이어 1800W", top_k=2)

    assert embedded == ["전기 헤어드라이어 1800W"]
    assert repo["vector"] == ([0.2] * 1536, "openai/text-embedding-3-small", 2)
    assert [(case.doc_id, distance) for case, distance in results] == [("1", 0.12), ("2", 0.3)]
    assert results[0][0] == CLIPCase(hs_codes=["8516310000"], product_name="품명1", description="설명",
                                     decision_reason="사유", doc_id="1", enforce_date="20240101")
    assert _Session.closed is True


def test_HS_코드로_겹치는_사례를_찾는다(repo):
    embedded = []

    cases = _database(embedded).find_by_hs_code("851631")

    assert repo["hs_code"] == "851631"
    assert [case.doc_id for case in cases] == ["1"]
    assert embedded == []
