"""전기 Tool 테스트 공용 Fake. 실제 법제처 응답을 저장한 픽스처로 법령 Client를 흉내 낸다."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas.clients.law_response import (
    AdmrulSearchResponse, LawAnnex, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.electrical.evidence import (
    NOTICE_ID, NOTICE_NAME, RULE_ID, RULE_NAME, LawApiEvidenceSource,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "electrical_law"
AS_OF = date(2026, 10, 7)
RULE_MST = "273575"
NOTICE_SERIAL = "2100000285148"
NEXT_NOTICE_SERIAL = "2100000283202"

_ANNEX_TITLES = {
    "0001": "안전인증대상전기용품 세부품목(제3조 관련)",
    "0002": "안전확인대상전기용품의 세부품목(제3조 관련)",
    "0003": "공급자적합성확인대상 전기용품의 세부품목(제3조 관련)",
}


def _articles(name: str) -> list[LawArticle]:
    return [LawArticle(**item) for item in json.loads((FIXTURES / name).read_text(encoding="utf-8"))]


class FakeLaw:
    """LawClient와 같은 메서드를 가진 Fake. 호출 기록과 오류 주입을 지원한다.

    검색 결과에는 실제처럼 2026-11-01 시행 예정 고시가 첫 행에 있다(검색 순서에 의존하는 구현을 잡는다).
    """

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.rule_search = LawSearchResponse(total_count=1, items=[
            dict(law_id=RULE_ID, law_name=RULE_NAME, mst=RULE_MST, enforce_date="20260827"),
        ])
        self.notice_search = AdmrulSearchResponse(total_count=2, items=[
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NEXT_NOTICE_SERIAL, enforce_date="20261101"),
            dict(rule_id=NOTICE_ID, name=NOTICE_NAME, serial_number=NOTICE_SERIAL, enforce_date="20260911"),
        ])
        self.rule_body = LawTextResponse(
            name=RULE_NAME, document_id=RULE_ID, enforce_date="20260827",
            articles=_articles("rule_article_3.json"),
            annexes=[LawAnnex(annex_type="별표", annex_number="0013", annex_branch_number="00",
                              annex_title="구매대행의 특례 제품(제56조 관련)",
                              annex_content=(FIXTURES / "rule_annex_13.txt").read_text(encoding="utf-8"))],
        )
        annexes = [
            LawAnnex(annex_type="별표", annex_number=number, annex_branch_number="00", annex_title=title,
                     annex_content=(FIXTURES / f"notice_annex_{int(number)}.txt").read_text(encoding="utf-8"))
            for number, title in _ANNEX_TITLES.items()
        ]
        self.notice_bodies = {
            serial: LawTextResponse(name=NOTICE_NAME, document_id=NOTICE_ID, enforce_date=day,
                                    articles=_articles("notice_article_3.json"), annexes=annexes)
            for serial, day in ((NOTICE_SERIAL, "20260911"), (NEXT_NOTICE_SERIAL, "20261101"))
        }

    def _call(self, method: str, key: str, result):
        self.calls.append((method, key))
        if self.error is not None:
            raise self.error
        return result

    def search_law(self, request):
        return self._call("search_law", request.query, self.rule_search)

    def get_law_text(self, request):
        return self._call("get_law_text", request.mst, self.rule_body)

    def search_admrul(self, request):
        return self._call("search_admrul", request.query, self.notice_search)

    def get_admrul_text(self, request):
        return self._call("get_admrul_text", request.mst, self.notice_bodies[request.mst])


@pytest.fixture
def fake_law() -> FakeLaw:
    return FakeLaw()


@pytest.fixture(scope="session")
def electrical_evidence():
    """실제 품목표 픽스처로 만든 근거. 파싱 비용이 있어 세션에 한 번 만든다."""
    return LawApiEvidenceSource(FakeLaw()).load(AS_OF)
