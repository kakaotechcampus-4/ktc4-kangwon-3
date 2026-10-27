"""법제처 조회 객체 묶음과 법령 점검 스케줄러를 DB·네트워크 없이 검증한다."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from app.config import LAW_SEARCH_RECHECK_SECONDS
from app.db import law_cache
from app.db.errors import DatabaseNotConfiguredError
from app.db.law_cache import KST, LawFetchers, build_law_fetchers, refresh_laws, run_law_refresh, seconds_until
from app.db.law_changes import LawChangeKind
from app.schemas.clients.law_response import (
    AdmrulSearchItem, AdmrulSearchResponse, LawSearchItem, LawSearchResponse,
)


@dataclass(frozen=True)
class _Source:
    name: str
    document_id: str
    is_admrul: bool


class _Fetcher:
    """refresh·fetch_parsed 호출을 기록하는 가짜 조회 객체."""

    def __init__(self, response=None, error: Exception | None = None, before=None):
        self.response = response
        self.error = error
        self.before = before
        self.refreshed = []
        self.fetched = []
        self.closed = False

    def cached(self, request):
        return self.before

    def refresh(self, request, accept=None):
        self.refreshed.append(request)
        if self.error is not None:
            raise self.error
        if accept is not None and not accept(self.response):
            raise LookupError("저장 조건에 맞지 않음")
        return self.response

    def fetch_parsed(self, request):
        self.fetched.append(request.mst)
        if self.error is not None:
            raise self.error

    def close(self):
        self.closed = True


def _law_search(*items: tuple[str, str]) -> LawSearchResponse:
    return LawSearchResponse(total_count=len(items), items=[
        LawSearchItem(mst=mst, law_id=law_id, law_name="법", enforce_date="20261203") for law_id, mst in items])


def _admrul_search(*items: tuple[str, str]) -> AdmrulSearchResponse:
    return AdmrulSearchResponse(total_count=len(items), items=[
        AdmrulSearchItem(serial_number=serial, rule_id=rule_id, name="고시") for rule_id, serial in items])


def _fetchers(**overrides) -> LawFetchers:
    parts = {"law_search": _Fetcher(_law_search()), "law_text": _Fetcher(),
             "admrul_search": _Fetcher(_admrul_search()), "admrul_text": _Fetcher()}
    return LawFetchers(**{**parts, **overrides})


def test_조회_객체는_검색은_시행법령_현행·시행예정만_점검_기한을_두고_본문은_영구_보관한다():
    fetchers = build_law_fetchers("test-oc", None)

    assert [f._name for f in fetchers] == ["law.eflaw_search", "law.text", "admrul.search", "admrul.text"]
    assert fetchers.law_search._client._extra_params() == {"nw": "2,3"}
    recheck = timedelta(seconds=LAW_SEARCH_RECHECK_SECONDS)
    assert [f._recheck_after for f in fetchers] == [recheck, None, recheck, None]
    fetchers.close()


def test_법령은_검색을_새로_받고_같은_ID의_현행·시행예정_본문을_모두_확보한다():
    fetchers = _fetchers(law_search=_Fetcher(_law_search(("012070", "100"), ("012070", "200"), ("099999", "300"))))

    report = refresh_laws(fetchers, [_Source("어린이제품 안전 특별법", "012070", is_admrul=False)])

    assert fetchers.law_search.refreshed[0].query == "어린이제품 안전 특별법"
    assert fetchers.law_search.refreshed[0].display == 100
    assert fetchers.law_text.fetched == ["100", "200"]
    assert (report.checked, report.versions, report.failed) == (1, 2, [])


def test_행정규칙은_행정규칙_검색과_본문을_쓴다():
    fetchers = _fetchers(admrul_search=_Fetcher(_admrul_search(("34911", "A"), ("34911", "B"))))

    report = refresh_laws(fetchers, [_Source("전기용품 및 생활용품 안전관리 운용요령", "34911", is_admrul=True)])

    assert fetchers.admrul_text.fetched == ["A", "B"]
    assert fetchers.law_search.refreshed == []
    assert report.versions == 2


def test_문서_하나가_실패해도_나머지는_점검한다():
    fetchers = _fetchers(law_search=_Fetcher(error=TimeoutError()),
                         admrul_search=_Fetcher(_admrul_search(("34911", "A"))))

    report = refresh_laws(fetchers, [_Source("전파법", "001732", False), _Source("운용요령", "34911", True)])

    assert report.failed == ["전파법"]
    assert fetchers.admrul_text.fetched == ["A"]


def test_검색_결과에_문서_ID가_없으면_실패로_남긴다():
    fetchers = _fetchers(law_search=_Fetcher(_law_search(("099999", "300"))))

    report = refresh_laws(fetchers, [_Source("전파법", "001732", False)])

    assert report.failed == ["전파법"]
    assert fetchers.law_text.fetched == []


def test_덮어쓰기_전_DB_목록과_비교한_변경을_한_번에_넘긴다():
    fetchers = _fetchers(law_search=_Fetcher(_law_search(("012070", "100"), ("012070", "200")),
                                             before=_law_search(("012070", "100"))))
    received = []

    report = refresh_laws(fetchers, [_Source("어린이제품 안전 특별법", "012070", False)], on_change=received.append)

    assert [(change.kind, change.version.version) for change in report.changes] == [(LawChangeKind.ANNOUNCED, "200")]
    assert received == [report.changes]


def test_변경을_넘기다_실패해도_점검_결과는_남는다():
    fetchers = _fetchers(law_search=_Fetcher(_law_search(("012070", "100"), ("012070", "200")),
                                             before=_law_search(("012070", "100"))))

    def broken(changes):
        raise RuntimeError("전달 실패")

    report = refresh_laws(fetchers, [_Source("어린이제품 안전 특별법", "012070", False)], on_change=broken)

    assert (report.versions, report.failed, len(report.changes)) == (2, [], 1)


@pytest.mark.parametrize(("now", "expected_hours"), [
    (datetime(2026, 10, 25, 0, 0, tzinfo=KST), 5 / 60),     # 오늘 0:05 전
    (datetime(2026, 10, 25, 0, 5, tzinfo=KST), 24),         # 정각이면 다음 날
    (datetime(2026, 10, 25, 12, 0, tzinfo=KST), 12 + 5 / 60),
])
def test_다음_점검_시각까지_남은_초(now, expected_hours):
    assert seconds_until(now, (0, 5)) == pytest.approx(expected_hours * 3600)


def test_기동_직후_한_번_점검하고_이후_매일_시각까지_기다린다():
    calls = []
    waits = []

    def refresh():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("첫 점검 실패")  # 실패해도 다음 점검은 계속

    async def sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            raise asyncio.CancelledError

    now = datetime(2026, 10, 25, 12, 0, tzinfo=KST)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_law_refresh(refresh, at=(0, 5), now=lambda: now, sleep=sleep))

    assert len(calls) == 2
    assert waits == [pytest.approx((12 + 5 / 60) * 3600)] * 2


def test_Tool용_조회_객체는_공용_DB_세션을_쓴다(monkeypatch):
    factory = object()
    monkeypatch.setattr(law_cache, "get_session_factory", lambda: factory)

    fetchers = law_cache.open_law_fetchers("test-oc")

    assert {f._session_factory for f in fetchers} == {factory}
    fetchers.close()


def test_DATABASE_URL이_없으면_Tool용_조회_객체는_클라이언트만_쓴다(monkeypatch):
    def not_configured():
        raise DatabaseNotConfiguredError("DATABASE_URL이 설정되지 않음")
    monkeypatch.setattr(law_cache, "get_session_factory", not_configured)

    fetchers = law_cache.open_law_fetchers("test-oc")

    assert {f._session_factory for f in fetchers} == {None}
    fetchers.close()
