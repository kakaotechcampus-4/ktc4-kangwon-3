"""식약 Tool 테스트 공용 Fake. 실제 법제처 응답을 저장한 픽스처로 법령 조회를 흉내 낸다."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawAnnex, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.food_drug.evidence import (
    COSMETICS_ACT, COSMETICS_NOTICE, COSMETICS_RULE, DEVICE_ACT, DEVICE_NOTICE, DEVICE_RULE, FOOD_ACT, HEALTH_FOOD_ACT,
    IMPORTED_FOOD_ACT, IMPORTED_FOOD_DECREE, load_food_drug_evidence,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "food_drug_law"
AS_OF = date(2026, 10, 15)
NOTICE_SERIAL = "2100000275656"
COSMETICS_SERIAL = "2100000276068"
# (문서, MST, 시행일, 조문 픽스처)
LAWS = {
    FOOD_ACT: ("285339", "20261008", "food_sanitation_act_articles.json"),
    IMPORTED_FOOD_ACT: ("285337", "20261008", "imported_food_act_articles.json"),
    IMPORTED_FOOD_DECREE: ("280513", "20251223", "imported_food_decree_articles.json"),
    DEVICE_ACT: ("285343", "20261008", "medical_device_act_articles.json"),
    DEVICE_RULE: ("287877", "20260701", "medical_device_rule_articles.json"),
    HEALTH_FOOD_ACT: ("285331", "20261008", "health_food_act_articles.json"),
    COSMETICS_ACT: ("285353", "20261008", "cosmetics_act_articles.json"),
    COSMETICS_RULE: ("285249", "20260402", "cosmetics_rule_articles.json"),
}


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeLaw:
    """LawApiClients와 같은 메서드를 가진 Fake. 의료기기법 검색에는 실제처럼 시행 예정 버전을 앞에 둔다."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.law_search: dict[str, LawSearchResponse] = {}
        self.law_bodies: dict[str, LawTextResponse] = {}
        for (name, law_id), (mst, day, fixture) in LAWS.items():
            items = [dict(law_id=law_id, law_name=name, mst=mst, enforce_date=day)]
            if (name, law_id) == DEVICE_ACT:
                items.insert(0, dict(law_id=law_id, law_name=name, mst="999999", enforce_date="20270101"))
            self.law_search[name] = LawSearchResponse(total_count=len(items), items=items)
            self.law_bodies[mst] = LawTextResponse(
                mst=mst, name=name, document_id=law_id, enforce_date=day,
                articles=[LawArticle(**item) for item in json.loads(_text(fixture))])
        self.notice_search = {
            DEVICE_NOTICE[0]: AdmrulSearchResponse(total_count=1, items=[
                dict(rule_id=DEVICE_NOTICE[1], name=DEVICE_NOTICE[0], serial_number=NOTICE_SERIAL,
                     enforce_date="20260309")]),
            COSMETICS_NOTICE[0]: AdmrulSearchResponse(total_count=1, items=[
                dict(rule_id=COSMETICS_NOTICE[1], name=COSMETICS_NOTICE[0], serial_number=COSMETICS_SERIAL,
                     enforce_date="20260318")]),
        }
        self.notice_bodies = {
            NOTICE_SERIAL: AdmrulTextResponse(
                serial_number=NOTICE_SERIAL, name=DEVICE_NOTICE[0], document_id=DEVICE_NOTICE[1],
                enforce_date="20260309", is_article_format=True, articles=[],
                annexes=[LawAnnex(annex_type="별표", annex_number="0001", annex_branch_number="00",
                                  annex_title="의료기기 품목 및 품목별 등급",
                                  annex_content=_text("device_grade_annex_1.txt"))]),
            COSMETICS_SERIAL: AdmrulTextResponse(
                serial_number=COSMETICS_SERIAL, name=COSMETICS_NOTICE[0], document_id=COSMETICS_NOTICE[1],
                enforce_date="20260318", is_article_format=True,
                articles=[LawArticle(**item) for item in json.loads(_text("cosmetic_safety_articles.json"))],
                annexes=[LawAnnex(annex_type="별표", annex_number="0001", annex_branch_number="00",
                                  annex_title="사용할 수 없는 원료",
                                  annex_content=_text("cosmetic_banned_annex_1.txt"))]),
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
        return self._call("search_admrul", request.query, self.notice_search[request.query])

    def get_admrul_text(self, request):
        return self._call("get_admrul_text", request.mst, self.notice_bodies[request.mst])


@pytest.fixture
def fake_law() -> FakeLaw:
    return FakeLaw()


@pytest.fixture(scope="session")
def food_drug_evidence():
    """실제 픽스처로 만든 근거. 별표 파싱 비용이 있어 세션에 한 번 만든다."""
    return load_food_drug_evidence(FakeLaw(), AS_OF)
