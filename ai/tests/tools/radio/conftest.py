"""전파 Tool 테스트 공용 Fake. 실제 법제처 응답을 저장한 픽스처로 법령 조회를 흉내 낸다."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawAnnex, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.radio.evidence import (
    DECREE_ID, DECREE_NAME, LAW_ID, LAW_NAME, NOTICE_ID, NOTICE_NAME, load_radio_evidence,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "radio_law"
AS_OF = date(2026, 10, 14)
LAW_MST = "276245"
DECREE_MST = "278235"
NOTICE_SERIAL = "2100000282888"
NEXT_NOTICE_SERIAL = "2100000267100"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeLaw:
    """LawApiClients와 같은 메서드를 가진 Fake. 고시 검색에는 실제처럼 2026-11-06 시행 예정본이 함께 온다."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.law_search = {
            LAW_NAME: LawSearchResponse(total_count=1, items=[
                dict(law_id=LAW_ID, law_name=LAW_NAME, mst=LAW_MST, enforce_date="20260102")]),
            DECREE_NAME: LawSearchResponse(total_count=1, items=[
                dict(law_id=DECREE_ID, law_name=DECREE_NAME, mst=DECREE_MST, enforce_date="20251001")]),
        }
        self.law_bodies = {
            LAW_MST: LawTextResponse(
                mst=LAW_MST, name=LAW_NAME, document_id=LAW_ID, enforce_date="20260102",
                articles=[LawArticle(**item) for item in json.loads(_text("law_article_58_2.json"))]),
            DECREE_MST: LawTextResponse(
                mst=DECREE_MST, name=DECREE_NAME, document_id=DECREE_ID, enforce_date="20251001", articles=[],
                annexes=[LawAnnex(annex_type="별표", annex_number="0006", annex_branch_number="02",
                                  annex_title="적합성평가 면제대상 기자재", annex_content=_text("decree_annex_6_2.txt"))]),
        }
        self.notice_search = AdmrulSearchResponse(total_count=2, items=[
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NEXT_NOTICE_SERIAL, enforce_date="20261106"),
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NOTICE_SERIAL, enforce_date="20260724"),
        ])
        annex = LawAnnex(annex_type="별표", annex_number="0001", annex_branch_number="00",
                         annex_title="적합성평가 대상기자재(제3조 관련)", annex_content=_text("notice_annex_1.txt"))
        self.notice_bodies = {
            serial: AdmrulTextResponse(serial_number=serial, name=NOTICE_NAME, document_id=NOTICE_ID,
                                       enforce_date=day, is_article_format=True, articles=[], annexes=[annex])
            for serial, day in ((NOTICE_SERIAL, "20260724"), (NEXT_NOTICE_SERIAL, "20261106"))
        }

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
        return self._call("get_admrul_text", request.mst, self.notice_bodies[request.mst])


@pytest.fixture
def fake_law() -> FakeLaw:
    return FakeLaw()


@pytest.fixture(scope="session")
def radio_evidence():
    return load_radio_evidence(FakeLaw(), AS_OF)
