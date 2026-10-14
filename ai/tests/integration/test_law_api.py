"""법제처 실제 API 호출 테스트."""

import pytest

from app.clients.law import LawSearchClient, LawTextClient
from app.schemas.clients.law_request import LawSearchRequest, LawTextRequest

pytestmark = pytest.mark.external_api

ELECTRICAL_RULE = "전기용품 및 생활용품 안전관리법 시행규칙"


def test_현행_법령을_검색해_본문을_조문과_별표까지_받는다(law_oc):
    search = LawSearchClient(oc=law_oc).fetch_parsed(LawSearchRequest(query=ELECTRICAL_RULE))
    current = next(item for item in search.items if item.law_name == ELECTRICAL_RULE and item.history_status == "현행")

    result = LawTextClient(oc=law_oc).fetch_parsed(LawTextRequest(mst=current.mst))

    assert result.mst == current.mst
    assert result.articles and all(article.headings for article in result.articles)
    # 품목표(안전인증대상제품)는 조문이 아니라 별표에 있음
    annex = next(a for a in result.annexes if a.annex_title and "안전인증대상제품" in a.annex_title)
    assert annex.file_type == "pdf"
