"""법령 점검의 변경 탐지를 검색 응답만으로 검증한다."""

from dataclasses import dataclass
from datetime import date

from app.db.law_changes import LawChangeKind, detect_changes, versions_of
from app.schemas.clients.law_response import AdmrulSearchItem, AdmrulSearchResponse, LawSearchItem, LawSearchResponse


@dataclass(frozen=True)
class _Source:
    name: str
    document_id: str
    is_admrul: bool
    tool: str


LAW = _Source("식품위생법", "001805", False, "food_drug_safety")
NOTICE = _Source("전기용품 및 생활용품 안전관리 운용요령", "34911", True, "electrical_safety")


def _laws(*rows):
    return LawSearchResponse(total_count=len(rows), items=[
        LawSearchItem(mst=mst, law_id=LAW.document_id, law_name=LAW.name, promulgate_date=issued, enforce_date=enforced)
        for mst, issued, enforced in rows])


def _notices(*rows):
    return AdmrulSearchResponse(total_count=len(rows), items=[
        AdmrulSearchItem(serial_number=serial, rule_id=NOTICE.document_id, name=NOTICE.name, issue_date=issued,
                         enforce_date=enforced)
        for serial, issued, enforced in rows])


def _latest_issued(source, response, as_of):
    rows = [v for v in versions_of(source, response) if v.enforce_date <= as_of.strftime("%Y%m%d")]
    return max(rows, key=lambda v: (v.issued_date, v.enforce_date)).version if rows else None


def _kinds(changes):
    return [(change.kind, change.version.version, change.previous) for change in changes]


CURRENT, PENDING = ("285339", "20260407", "20261008"), ("282007", "20251230", "20261231")


def test_DB_목록에_없던_판은_새_판_발표로_낸다():
    changes = detect_changes(LAW, _laws(CURRENT), _laws(CURRENT, PENDING), today=date(2026, 10, 27), select=None)

    assert _kinds(changes) == [(LawChangeKind.ANNOUNCED, "282007", None)]
    assert changes[0].tool == "food_drug_safety"


def test_처음_점검이면_새_판_발표를_내지_않는다():
    assert detect_changes(LAW, None, _laws(CURRENT, PENDING), today=date(2026, 10, 27), select=None) == []


def test_시행일이_와서_적용_판이_바뀌면_이전_판과_함께_낸다():
    before = after = _laws(("276551", "20251001", "20251001"), ("280051", "20251202", "20261203"))

    changes = detect_changes(LAW, before, after, today=date(2026, 12, 3), select=_latest_issued)

    assert _kinds(changes) == [(LawChangeKind.APPLIED, "280051", "276551")]


def test_시행일이_왔지만_나중_공포_판이_있어_건너뛰면_확인_필요로_낸다():
    listed = _laws(CURRENT, PENDING)

    changes = detect_changes(LAW, listed, listed, today=date(2026, 12, 31), select=_latest_issued)

    assert _kinds(changes) == [(LawChangeKind.SKIPPED, "282007", None)]


def test_행정규칙도_발령일로_같은_변경을_찾는다():
    listed = _notices(("2100000285148", "20260911", "20260911"), ("2100000283202", "20260731", "20261101"))

    assert _kinds(detect_changes(NOTICE, listed, listed, today=date(2026, 11, 1), select=_latest_issued)) == [
        (LawChangeKind.SKIPPED, "2100000283202", None)]
    assert detect_changes(NOTICE, listed, listed, today=date(2026, 11, 2), select=_latest_issued) == []
