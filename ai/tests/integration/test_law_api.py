"""법제처 실제 API 호출 테스트."""

import pytest

from app.clients.law import AnnexFileClient, LawSearchClient, LawTextClient
from app.schemas.clients.law_request import AnnexFileRequest, LawSearchRequest, LawTextRequest
from app.utils.annex_file import Table, read_annex_file

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
    # 표 구조가 남는 HWP 링크를 PDF보다 먼저 고름
    assert annex.file_type == "hwp"


def test_별표_원본_파일을_받아_칸이_병합된_표로_읽는다(law_oc):
    search = LawSearchClient(oc=law_oc).fetch_parsed(LawSearchRequest(query=ELECTRICAL_RULE))
    current = next(item for item in search.items if item.law_name == ELECTRICAL_RULE and item.history_status == "현행")
    text = LawTextClient(oc=law_oc).fetch_parsed(LawTextRequest(mst=current.mst))
    annex = next(a for a in text.annexes if a.annex_title and "안전인증대상제품" in a.annex_title)

    file = AnnexFileClient().fetch_parsed(AnnexFileRequest(file_url=annex.file_url))
    blocks = read_annex_file(file.content, file.file_type)

    table = next(block for block in blocks if isinstance(block, Table))
    header = next(row for row in table.grid() if row[0].text == "분류")
    # 분류 칸은 두 열, 분류 값 칸은 품목·비고 행에 걸쳐 병합돼 있음
    assert [cell.text for cell in header] == ["분류", "분류", "품목"]
    assert any(cell.row_span > 1 for cell in table.cells if cell.col == 0)
