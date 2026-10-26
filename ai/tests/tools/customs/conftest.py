"""통관 Tool 테스트 공용 Fake. 실제 법제처·CLIP 응답을 저장한 픽스처로 조회를 흉내 낸다."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas.clients.customs_response import CLIPSearchResponse
from app.schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawAnnex, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.common.law import EvidenceUnavailable
from app.tools.customs.evidence import (
    ACT_ID, ACT_NAME, DECREE_ID, DECREE_NAME, NOTICE_ID, NOTICE_NAME, load_customs_evidence,
)
from app.tools.customs.search import Requirement

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "customs_law"
AS_OF = date(2026, 10, 15)
ACT_MST = "290673"
DECREE_MST = "290379"
NOTICE_SERIAL = "2100000282502"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _articles(name: str) -> list[LawArticle]:
    return [LawArticle(**item) for item in json.loads(_text(name))]


def _annex(number: int, title: str) -> LawAnnex:
    return LawAnnex(annex_type="별표", annex_number=f"{number:04d}", annex_branch_number="00",
                    annex_title=title, annex_content=_text(f"notice_annex_{number}.txt"))


class FakeLaw:
    """LawApiClients와 같은 메서드를 가진 Fake. 관세법 검색에는 실제처럼 시행 예정 버전을 앞에 둔다."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.law_search = {
            ACT_NAME: LawSearchResponse(total_count=2, items=[
                dict(law_id=ACT_ID, law_name=ACT_NAME, mst="999999", enforce_date="20270101"),
                dict(law_id=ACT_ID, law_name=ACT_NAME, mst=ACT_MST, enforce_date="20261002")]),
            DECREE_NAME: LawSearchResponse(total_count=1, items=[
                dict(law_id=DECREE_ID, law_name=DECREE_NAME, mst=DECREE_MST, enforce_date="20261002")]),
        }
        self.law_bodies = {
            ACT_MST: LawTextResponse(mst=ACT_MST, name=ACT_NAME, document_id=ACT_ID, enforce_date="20261002",
                                     articles=_articles("customs_act_article_226.json")),
            DECREE_MST: LawTextResponse(mst=DECREE_MST, name=DECREE_NAME, document_id=DECREE_ID,
                                        enforce_date="20261002", articles=_articles("trade_decree_article_19.json")),
        }
        self.notice_search = AdmrulSearchResponse(total_count=1, items=[
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NOTICE_SERIAL, enforce_date="20260716")])
        self.notice_body = AdmrulTextResponse(
            serial_number=NOTICE_SERIAL, name=NOTICE_NAME, document_id=NOTICE_ID, enforce_date="20260716",
            is_article_format=True, articles=_articles("notice_articles.json"),
            annexes=[_annex(2, "세관장확인대상 수입물품"), _annex(5, "세관장확인생략 대상 법령 및 수출입자")])

    def _call(self, method: str, key: str, result):
        self.calls.append((method, key))
        if self.error is not None:
            raise self.error
        return result

    def search_law(self, request):
        return self._call("search_law", request.query, self.law_search[request.query])

    def get_law_text(self, request):
        return self._call("get_law_text", request.mst, self.law_bodies[request.mst])

    def search_admrul(self, request):
        return self._call("search_admrul", request.query, self.notice_search)

    def get_admrul_text(self, request):
        return self._call("get_admrul_text", request.mst, self.notice_body)


class FakeClip:
    """CLIPClient 대신 쓰는 Fake. 저장한 검색어별 응답을 돌려주고, 없는 검색어는 빈 결과다."""

    responses = {query: CLIPSearchResponse(**body) for query, body in json.loads(_text("clip_cases.json")).items()}

    def __init__(self, calls: list[str], errors: dict[str, Exception]):
        self.calls, self.errors = calls, errors
        self.closed = False

    def fetch_parsed(self, request):
        self.calls.append(request.query)
        if request.query in self.errors:
            raise self.errors[request.query]
        return self.responses.get(request.query, CLIPSearchResponse(page=1, total_count=0, has_next=False, items=[]))

    def close(self):
        self.closed = True


class FakeRequirements:
    """세관장확인 GW 대신 HS별 요건을 돌려준다. 형식은 tests/clients/customs/test_gw.py의 실제 응답 형식을 따른다."""

    ELECTRICAL = Requirement(hs_code="8516799000", law_name="전기용품 및 생활용품 안전관리법", agency="국가기술표준원",
                             document="전기용품 및 생활용품 요건확인서", apply_start_date="20200406")
    RADIO = Requirement(hs_code="8516799000", law_name="전파법", agency="국립전파연구원",
                        document="적합성평가 확인서", apply_start_date="20200406")
    FOOD = Requirement(hs_code="3924100000", law_name="수입식품안전관리 특별법", agency="식품의약품안전처",
                       document="수입식품등의 수입신고확인증", apply_start_date="20200406")

    def __init__(self, table: dict[str, list[Requirement]] | None = None, error: Exception | None = None):
        self.table = table if table is not None else {"8516799000": [self.ELECTRICAL], "3924100000": [self.FOOD]}
        self.error = error
        self.calls: list[str] = []

    def lookup(self, hs_code: str) -> list[Requirement]:
        self.calls.append(hs_code)
        if self.error is not None:
            raise self.error
        return list(self.table.get(hs_code, []))


@pytest.fixture
def fake_law() -> FakeLaw:
    return FakeLaw()


@pytest.fixture(scope="session")
def customs_evidence():
    return load_customs_evidence(FakeLaw(), AS_OF)


__all__ = ["AS_OF", "EvidenceUnavailable", "FakeClip", "FakeLaw", "FakeRequirements"]
