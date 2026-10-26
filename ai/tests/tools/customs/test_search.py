"""결정사례 조회(CLIP)와 세관장확인 요건 조회(GW)를 네트워크 없이 확인한다."""

import httpx
import pytest

from app.schemas.clients.customs_response import CustomsGwConfirmation, CustomsGwConfirmationResponse
from app.tools.common.law import EvidenceUnavailable
from app.tools.customs.search import ClipCaseSearch, DatabaseCaseSearch, GwRequirementLookup

from .conftest import FakeClip

SPATULA_CASE = "0072017003150"   # 3924.10-0000 실리콘 주걱(손잡이 너도밤나무)


def clip(errors=None):
    calls, clients = [], []

    def factory():
        client = FakeClip(calls, errors or {})
        clients.append(client)
        return client

    return ClipCaseSearch(factory), calls, clients


def test_검색어별로_받아_합친_뒤_상품_용어와_비슷한_사례를_고른다():
    search, calls, clients = clip()
    found = search.search(["실리콘 주걱", "주방용품"], ["실리콘 주걱", "실리콘"], top_k=5)
    assert sorted(calls) == ["실리콘 주걱", "주방용품"]
    assert SPATULA_CASE in [case.case_id for case in found.cases]
    assert all(case.hs_codes for case in found.cases)
    assert all(client.closed for client in clients)


def test_일부_검색어가_시간_초과여도_나머지로_찾고_실패한_검색어를_남긴다():
    search, _, _ = clip({"주방용품": httpx.ReadTimeout("느림")})
    found = search.search(["실리콘 주걱", "주방용품"], ["실리콘 주걱"], top_k=5)
    assert found.failed_terms == ("주방용품",)
    assert SPATULA_CASE in [case.case_id for case in found.cases]


def test_모든_검색어가_실패하면_오류를_올린다():
    search, _, _ = clip({"실리콘 주걱": httpx.ReadTimeout("느림")})
    with pytest.raises(httpx.ReadTimeout):
        search.search(["실리콘 주걱"], ["실리콘 주걱"], top_k=5)


def test_검색어가_없으면_조회하지_않는다():
    search, calls, _ = clip()
    assert search.search([" ", ""], ["주걱"], top_k=5).cases == ()
    assert calls == []


def test_결정사례_DB_조회는_아직_스텁이다():
    with pytest.raises(NotImplementedError):
        DatabaseCaseSearch(session_factory=None).search(["주걱"], ["주걱"], top_k=5)


class _Gw:
    def __init__(self, calls):
        self.calls = calls

    def fetch_parsed(self, request):
        self.calls.append(request.hs_code)
        return CustomsGwConfirmationResponse(items=[
            CustomsGwConfirmation(hs_code=request.hs_code, law_name="전파법", req_agency_name="국립전파연구원",
                                  req_document_name="적합성평가 확인서", apply_start_date="20200406"),
            CustomsGwConfirmation(hs_code=request.hs_code, law_name=None),
        ])

    def close(self):
        self.calls.append("close")


def test_GW_응답을_요건으로_옮기고_HS별로_캐시한다():
    calls, now = [], [0.0]
    lookup = GwRequirementLookup("key", ttl_seconds=10, clock=lambda: now[0], client_factory=lambda key: _Gw(calls))
    first = lookup.lookup("8518301000")
    assert [(item.law_name, item.agency, item.document) for item in first] == [
        ("전파법", "국립전파연구원", "적합성평가 확인서")]  # 법령명이 없는 행은 뺀다
    assert lookup.lookup("8518301000") == first and calls == ["8518301000", "close"]
    now[0] = 11
    lookup.lookup("8518301000")
    assert calls.count("8518301000") == 2


def test_서비스_키가_없으면_조회할_수_없다고_알린다():
    with pytest.raises(EvidenceUnavailable, match="DATA_GO_KR_KEY"):
        GwRequirementLookup(None).lookup("8518301000")
