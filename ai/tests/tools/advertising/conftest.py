"""표시·광고 Tool 테스트 공용 Fake. 실제 법제처 응답을 저장한 픽스처로 법령 조회를 흉내 낸다."""

import json
from pathlib import Path

import pytest

from app.schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawArticle, LawSearchResponse, LawTextResponse,
)
from app.tools.advertising.evidence import (
    AWARD_CERT_GUIDELINE, CONSUMER_SAFETY_GUIDELINE, DESIGNATION_NOTICE, LAW_ACT, SUBSTANTIATION_NOTICE,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "advertising_law"
LAW_MST = "268659"
LAW_ENFORCE_DATE = "20250121"
# (문서, 일련번호, 시행일, 본문 픽스처)
NOTICES = (
    (DESIGNATION_NOTICE, "2100000184414", "20191212", "notice_designation.txt"),
    (SUBSTANTIATION_NOTICE, "2100000284664", "20260903", "notice_substantiation.txt"),
    (AWARD_CERT_GUIDELINE, "2100000070475", "20161223", "guideline_award_cert.txt"),
    (CONSUMER_SAFETY_GUIDELINE, "2100000056062", "20160803", "guideline_consumer_safety.txt"),
)


class FakeLaw:
    """LawApiClients와 같은 메서드를 가진 Fake. 행정규칙 본문은 실제 응답처럼 조문 하나에 전체가 들어 있다."""

    def __init__(self) -> None:
        name, law_id = LAW_ACT
        self.law_search = LawSearchResponse(total_count=1, items=[
            dict(law_id=law_id, law_name=name, mst=LAW_MST, enforce_date=LAW_ENFORCE_DATE,
                 promulgate_date=LAW_ENFORCE_DATE)])
        articles = json.loads((FIXTURES / "law_articles_3_5.json").read_text(encoding="utf-8"))
        self.law_bodies = {LAW_MST: LawTextResponse(
            mst=LAW_MST, name=name, document_id=law_id, enforce_date=LAW_ENFORCE_DATE,
            articles=[LawArticle(**article) for article in articles])}
        self.notice_search: dict[str, AdmrulSearchResponse] = {}
        self.notice_bodies: dict[str, AdmrulTextResponse] = {}
        for (name, rule_id), serial, day, fixture in NOTICES:
            self.notice_search[name] = AdmrulSearchResponse(total_count=1, items=[
                dict(rule_id=rule_id, name=name, serial_number=serial, enforce_date=day, issue_date=day)])
            self.notice_bodies[serial] = self.notice_body(
                (name, rule_id), serial, day, (FIXTURES / fixture).read_text(encoding="utf-8"))

    @staticmethod
    def notice_body(document: tuple[str, str], serial: str, day: str, text: str) -> AdmrulTextResponse:
        """본문 전체가 조문 하나에 들어 있는 행정규칙 응답을 만든다.

        Args:
            document: (문서 이름, 행정규칙ID).
            serial: 일련번호.
            day: 시행일.
            text: 본문 전체.

        Returns:
            AdmrulTextResponse: 본문 응답.
        """
        name, rule_id = document
        return AdmrulTextResponse(serial_number=serial, name=name, document_id=rule_id, enforce_date=day,
                                  is_article_format=False, articles=[LawArticle(article_content=text)])

    def search_law(self, request) -> LawSearchResponse:
        return self.law_search

    def get_law_text(self, request) -> LawTextResponse:
        return self.law_bodies[request.mst]

    def search_admrul(self, request) -> AdmrulSearchResponse:
        return self.notice_search[request.query]

    def get_admrul_text(self, request) -> AdmrulTextResponse:
        return self.notice_bodies[request.mst]


@pytest.fixture
def law() -> FakeLaw:
    return FakeLaw()
