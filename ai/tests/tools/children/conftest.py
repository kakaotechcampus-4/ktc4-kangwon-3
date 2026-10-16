"""어린이제품 Tool 테스트 공용 Fake. 실제 법제처 응답을 저장한 픽스처로 법령 조회를 흉내 낸다."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawAnnex, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.children.evidence import (
    LAW_ID, LAW_NAME, NOTICE_ID, NOTICE_NAME, RULE_ID, RULE_NAME, load_children_evidence,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "children_law"
AS_OF = date(2026, 10, 14)
LAW_MST = "276551"
RULE_MST = "286387"
NOTICE_SERIAL = "2100000254530"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _annex(number: int, name: str) -> LawAnnex:
    return LawAnnex(annex_type="별표", annex_number=f"{number:04d}", annex_branch_number="00",
                    annex_title=f"별표 {number}", annex_content=_text(name))


class FakeLaw:
    """LawApiClients와 같은 메서드를 가진 Fake. 호출 기록과 오류 주입을 지원한다.

    시행규칙 검색에는 실제처럼 시행 예정 버전을 앞에 둔다(검색 순서에 의존하는 구현을 잡는다).
    """

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.law_search = {
            LAW_NAME: LawSearchResponse(total_count=1, items=[
                dict(law_id=LAW_ID, law_name=LAW_NAME, mst=LAW_MST, enforce_date="20251001")]),
            RULE_NAME: LawSearchResponse(total_count=2, items=[
                dict(law_id=RULE_ID, law_name=RULE_NAME, mst="999999", enforce_date="20270101"),
                dict(law_id=RULE_ID, law_name=RULE_NAME, mst=RULE_MST, enforce_date="20260603")]),
        }
        self.law_bodies = {
            LAW_MST: LawTextResponse(
                mst=LAW_MST, name=LAW_NAME, document_id=LAW_ID, enforce_date="20251001",
                articles=[LawArticle(**item) for item in json.loads(_text("law_article_2.json"))]),
            RULE_MST: LawTextResponse(
                mst=RULE_MST, name=RULE_NAME, document_id=RULE_ID, enforce_date="20260603", articles=[],
                annexes=[_annex(number, f"rule_annex_{number}.txt") for number in (1, 2, 3)]),
        }
        self.notice_search = AdmrulSearchResponse(total_count=1, items=[
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NOTICE_SERIAL, enforce_date="20240710")])
        self.notice_body = AdmrulTextResponse(
            serial_number=NOTICE_SERIAL, name=NOTICE_NAME, document_id=NOTICE_ID, enforce_date="20240710",
            is_article_format=True, articles=[],
            annexes=[_annex(number, f"notice_annex_{number}.txt") for number in (3, 4, 5)])

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


@pytest.fixture
def fake_law() -> FakeLaw:
    return FakeLaw()


@pytest.fixture(scope="session")
def children_evidence():
    """실제 픽스처로 만든 근거. 파싱 비용이 있어 세션에 한 번 만든다."""
    return load_children_evidence(FakeLaw(), AS_OF)
