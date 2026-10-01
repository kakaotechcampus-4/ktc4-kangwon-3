"""법제처 실제 API 호출 테스트."""

import pytest

from app.clients.law import LawClient
from app.schemas.clients.law_request import LawTextRequest

pytestmark = pytest.mark.integration

# 전기용품 및 생활용품 안전관리법 시행규칙 (품목표 별표 3·4 포함)
ELECTRICAL_RULE_MST = "273575"


def test_법령_본문을_조문과_별표까지_받는다(law_oc):
    result = LawClient(oc=law_oc).get_law_text(LawTextRequest(mst=ELECTRICAL_RULE_MST))

    assert result.articles
    assert any(annex.annex_title and "안전인증대상제품" in annex.annex_title for annex in result.annexes)
