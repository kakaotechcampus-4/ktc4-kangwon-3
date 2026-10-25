"""CLIP 결정사례 적재 루틴을 DB·네트워크 없이 검증한다."""

import pytest

from app.db import clip_ingest
from app.db.clip_ingest import ALL_CASES_QUERY, case_text, collect_doc_ids, ingest_clip_cases
from app.schemas.clients.customs_response import CLIPCase, CLIPSearchResponse


def _case(doc_id: str, **overrides) -> CLIPCase:
    fields = {"hs_codes": ["8516310000"], "product_name": f"품명{doc_id}", "description": "설명",
              "decision_reason": "사유", "doc_id": doc_id, "enforce_date": "20240101"}
    return CLIPCase(**{**fields, **overrides})


class _Search:
    """페이지마다 정해 둔 문서 ID를 돌려주는 가짜 검색. 처음 몇 번은 빈 페이지를 줄 수 있음."""

    def __init__(self, pages: list[list[str]], total: int, empty_first: dict[int, int] | None = None):
        self.pages = pages
        self.total = total
        self.empty_first = dict(empty_first or {})
        self.requests = []

    def fetch_parsed(self, request):
        self.requests.append(request)
        if self.empty_first.get(request.page, 0) > 0:
            self.empty_first[request.page] -= 1
            return CLIPSearchResponse(page=request.page, total_count=0, has_next=False, items=[])
        ids = self.pages[request.page - 1]
        return CLIPSearchResponse(page=request.page, total_count=self.total, has_next=True,
                                  items=[_case(doc_id) for doc_id in ids])


class _Detail:
    def __init__(self, failing: set[str] = frozenset()):
        self.failing = failing
        self.requested = []

    def fetch_parsed(self, request):
        self.requested.append(request.doc_id)
        if request.doc_id in self.failing:
            raise RuntimeError("상세 실패")
        return _case(request.doc_id, description=f"전문{request.doc_id}")


class _Session:
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        _Session.commits += 1


@pytest.fixture
def db(monkeypatch):
    """HsCaseRepository를 가짜로 바꾸고, 이미 있는 문서와 저장된 행을 기록한다."""
    state = {"existing": set(), "saved": []}

    class _Repository:
        def __init__(self, session):
            pass

        def list_doc_ids(self):
            return set(state["existing"])

        def upsert_many(self, cases):
            state["saved"].append(cases)

    _Session.commits = 0
    monkeypatch.setattr(clip_ingest, "HsCaseRepository", _Repository)
    return state


def _no_sleep(seconds):
    pass


def test_목록은_검색어_공백으로_전체_페이지를_받아_중복_없이_모은다():
    search = _Search([["1", "2"], ["2", "3"], ["4"]], total=205)

    assert collect_doc_ids(search, workers=2, sleep=_no_sleep) == ["1", "2", "3", "4"]
    assert {r.query for r in search.requests} == {ALL_CASES_QUERY}
    assert sorted(r.page for r in search.requests) == [1, 2, 3]
    assert {r.page_size for r in search.requests} == {100}


def test_빈_페이지는_다시_받는다():
    search = _Search([["1"], ["2"]], total=101, empty_first={2: 2})

    assert collect_doc_ids(search, workers=1, sleep=_no_sleep) == ["1", "2"]


def test_다시_받아도_비어_있으면_목록이_불완전하다고_알린다():
    search = _Search([["1"], ["2"]], total=101, empty_first={2: 3})

    with pytest.raises(RuntimeError, match="2페이지가 비어"):
        collect_doc_ids(search, workers=1, sleep=_no_sleep)


def test_임베딩_입력은_품명·물품설명·결정사유_전문이다():
    assert case_text(_case("1", product_name=" 전기밥솥 ", description="", decision_reason="사유")) == "전기밥솥\n사유"


def test_DB에_없는_사례만_상세를_받아_묶음마다_임베딩하고_저장한다(db):
    db["existing"] = {"2"}
    detail = _Detail()
    embedded = []

    def embed(texts):
        embedded.append(texts)
        return [[0.1] * 1536 for _ in texts]

    report = ingest_clip_cases(
        search=_Search([["1", "2"], ["3", "4"], ["5"]], total=205), detail=detail, embed=embed,
        embedding_model="openai/text-embedding-3-small", session_factory=_Session, workers=2, chunk_size=2,
        sleep=_no_sleep)

    assert sorted(detail.requested) == ["1", "3", "4", "5"]
    assert [len(texts) for texts in embedded] == [2, 2]
    assert embedded[0][0] == "품명1\n전문1\n사유"
    assert [[row.doc_id for row in rows] for rows in db["saved"]] == [["1", "3"], ["4", "5"]]
    row = db["saved"][0][0]
    assert (row.embedding_model, row.hs_codes, row.enforce_date) == ("openai/text-embedding-3-small",
                                                                     ["8516310000"], "20240101")
    assert _Session.commits == 2
    assert (report.listed, report.existing, report.saved, report.failed) == (5, 1, 4, [])


def test_상세를_못_받은_사례는_빼고_실패로_남긴다(db):
    report = ingest_clip_cases(
        search=_Search([["1", "2", "3"]], total=3), detail=_Detail(failing={"2"}),
        embed=lambda texts: [[0.1] * 1536 for _ in texts], embedding_model="m", session_factory=_Session,
        sleep=_no_sleep)

    assert [row.doc_id for row in db["saved"][0]] == ["1", "3"]
    assert (report.saved, report.failed) == (2, ["2"])


def test_limit만큼만_새로_받는다(db):
    detail = _Detail()

    report = ingest_clip_cases(
        search=_Search([["1", "2", "3"]], total=3), detail=detail,
        embed=lambda texts: [[0.1] * 1536 for _ in texts], embedding_model="m", session_factory=_Session,
        limit=2, sleep=_no_sleep)

    assert sorted(detail.requested) == ["1", "2"]
    assert report.saved == 2
