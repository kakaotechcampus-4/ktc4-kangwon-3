"""공용 법령 조회(common/law.py): 시행일이 나뉜 개정판은 검색과 본문의 시행일이 다르게 온다."""

from datetime import date

import pytest

from app.schemas.clients.law_response import LawSearchItem, LawSearchResponse, LawTextResponse
from app.tools.common.law import EvidenceUnavailable, load_law, select_version

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


def _search(*rows):
    return LawSearchResponse(total_count=len(rows), items=[
        LawSearchItem(mst=mst, law_id=LAW_ID, law_name=NAME, promulgate_date=promulgated, enforce_date=enforced)
        for mst, promulgated, enforced in rows])


FOOD_ACT_ROWS = (("285339", "20260407", "20261008"), ("282007", "20251230", "20261231"))


@pytest.mark.parametrize("as_of,expected", [
    (date(2026, 10, 27), "285339"),
    (date(2026, 12, 31), "285339"),
])
def test_나중에_공포돼_먼저_시행된_판이_있으면_옛_공포_판으로_넘어가지_않는다(as_of, expected):
    selected = select_version(_search(*FOOD_ACT_ROWS), name=NAME, identifier=LAW_ID, id_field="law_id",
                              name_field="law_name", version_field="mst", as_of=as_of,
                              issued_field="promulgate_date")
    assert selected.mst == expected


def test_가장_나중에_공포된_판은_시행일이_되면_넘어간다():
    rows = (("276551", "20251001", "20251001"), ("280051", "20251202", "20261203"))
    select = lambda as_of: select_version(_search(*rows), name=NAME, identifier=LAW_ID, id_field="law_id",
                                          name_field="law_name", version_field="mst", as_of=as_of,
                                          issued_field="promulgate_date").mst
    assert (select(date(2026, 12, 2)), select(date(2026, 12, 3))) == ("276551", "280051")


def test_같은_공포_판의_시행일이_여럿이면_기준일에_맞는_시행일을_쓴다():
    rows = (("291321", "20261020", "20261020"), ("291321", "20261020", "20271231"),
            ("281933", "20251230", "20271231"), ("289781", "20260915", "20271231"))
    selected = select_version(_search(*rows), name=NAME, identifier=LAW_ID, id_field="law_id",
                              name_field="law_name", version_field="mst", as_of=date(2027, 12, 31),
                              issued_field="promulgate_date")
    assert (selected.mst, selected.enforce_date) == ("291321", "20271231")


def test_본문이_다른_문서면_쓰지_않는다():
    with pytest.raises(EvidenceUnavailable):
        load_law(FakeLaw("20261020", "20261020", body_id="000001"), name=NAME, law_id=LAW_ID, as_of=date(2026, 10, 20))
