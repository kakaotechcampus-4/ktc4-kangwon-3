"""공용 법령 조회(common/law.py): 시행일이 나뉜 개정판은 검색과 본문의 시행일이 다르게 온다."""

from datetime import date

import pytest

from app.schemas.clients.law_response import LawSearchItem, LawSearchResponse, LawTextResponse
from app.tools.common.law import EvidenceUnavailable, load_law

NAME, LAW_ID = "의료기기법", "009514"


class FakeLaw:
    def __init__(self, search_date: str, body_date: str, body_id: str = LAW_ID):
        self.search_date, self.body_date, self.body_id = search_date, body_date, body_id

    def search_law(self, request):
        item = LawSearchItem(mst="291321", law_id=LAW_ID, law_name=NAME, enforce_date=self.search_date)
        return LawSearchResponse(total_count=1, items=[item])

    def get_law_text(self, request):
        return LawTextResponse(mst=request.mst, name=NAME, document_id=self.body_id, enforce_date=self.body_date,
                               articles=[], annexes=[])


def test_시행일이_나뉜_개정판은_본문_시행일이_달라도_검색에서_고른_판을_쓴다():
    # 실측(2026-10-20): 검색 현행 20261020, 본문 20271021 (부칙상 일부 조문 나중 시행)
    document = load_law(FakeLaw("20261020", "20271021"), name=NAME, law_id=LAW_ID, as_of=date(2026, 10, 20))
    assert (document.version_id, document.enforce_date) == ("291321", "20261020")


def test_본문이_다른_문서면_쓰지_않는다():
    with pytest.raises(EvidenceUnavailable):
        load_law(FakeLaw("20261020", "20261020", body_id="000001"), name=NAME, law_id=LAW_ID, as_of=date(2026, 10, 20))
