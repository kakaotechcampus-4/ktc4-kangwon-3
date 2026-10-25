"""근거 문서 목록의 이름·ID가 실제 법제처 검색 결과와 짝이 맞는지 확인한다."""

import pytest

from app.clients.law import AdmrulSearchClient, LawSearchClient
from app.schemas.clients.law_request import LawSearchRequest
from app.tools.common.law_sources import LAW_SOURCES

pytestmark = pytest.mark.external_api


@pytest.mark.parametrize("source", LAW_SOURCES, ids=lambda source: source.name)
def test_문서_이름으로_검색하면_같은_ID의_문서가_나온다(source, law_oc):
    request = LawSearchRequest(query=source.name, display=100)
    if source.is_admrul:
        found = {(item.name, item.rule_id) for item in AdmrulSearchClient(oc=law_oc).fetch_parsed(request).items}
    else:
        found = {(item.law_name, item.law_id) for item in LawSearchClient(oc=law_oc).fetch_parsed(request).items}

    assert (source.name, source.document_id) in found
