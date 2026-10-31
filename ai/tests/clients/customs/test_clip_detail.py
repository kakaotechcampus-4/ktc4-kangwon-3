"""CLIP 품목분류 결정사례 상세 클라이언트를 실제 호출 없이 검증한다."""

from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from app.clients.customs import CLIPDetailClient
from app.schemas.clients.customs_request import CLIPDetailRequest


def _page(*, hs: str = "3304.99-1000", enforce: str = "19881228", description: str = "백색크림상.",
          reason: str = "피부보호제이므로 제3304.99-1000호에 분류") -> str:
    # 실제 응답(raw.html)의 표 구조를 줄인 것
    return f"""
    <table id="ULS0203037S_T1_table1"><tbody>
      <tr><th scope="row">참조번호</th><td class="textLeft hlzone1">감정22701-3300</td></tr>
      <tr><th scope="row">시행일자</th><td class="textLeft">
          1988-12-28 <input type="hidden" name="txtEnfrDt" value="{enforce}"/></td></tr>
      <tr><th scope="row">결정세번</th><td class="textLeft hlzone3">
          {hs} <input type="hidden" name="txtDtrmHsSgn" value="{hs}"/>
          <button type="button" name="btnTrrtPop"><span>관세율표</span></button></td></tr>
      <tr><th scope="row">품명</th><td class="textLeft hlzone4">
          Skin care cosmetic (SBS-44)
      </td></tr>
      <tr><th scope="row">물품설명</th><td class="textLeft hlzone5">
          {description}
      </td></tr>
      <tr><th scope="row">결정사유</th><td class="textLeft hlzone6">
          {reason}
      </td></tr>
      <tr><th scope="row">이미지건수</th><td class="textLeft">0</td></tr>
    </tbody></table>"""


def _responding(page: str):
    return lambda request: httpx.Response(200, text=page, headers={"content-type": "text/html;charset=UTF-8"})


def test_상세는_form으로_문서_ID를_보낸다(wire):
    client = CLIPDetailClient()
    sent = wire(client, _responding(_page()))

    client.fetch_raw(CLIPDetailRequest(doc_id="0001988800175"))

    assert sent[0].method == "POST"
    assert str(sent[0].url) == "https://unipass.customs.go.kr/clip/prlstclsfsrch/retrieveDmstPrlstClsfCaseDtl.do"
    assert parse_qs(sent[0].content.decode()) == {"rrdcNo": ["0001988800175"]}


def test_상세는_검색_항목과_같은_모양으로_전문을_돌려준다(wire):
    client = CLIPDetailClient()
    wire(client, _responding(_page(description="Water,  Petrolatum&amp;Kaolin<br/>플라스틱 튜브에   소매포장")))

    case = client.fetch_parsed(CLIPDetailRequest(doc_id="0001988800175"))

    assert case.model_dump() == {
        "hs_codes": ["3304991000"],
        "product_name": "Skin care cosmetic (SBS-44)",
        # <br>은 줄바꿈, 줄 안 공백은 하나로, HTML 엔티티는 글자로
        "description": "Water, Petrolatum&Kaolin\n플라스틱 튜브에 소매포장",
        "decision_reason": "피부보호제이므로 제3304.99-1000호에 분류",
        "doc_id": "0001988800175",
        "enforce_date": "19881228",
    }


def test_구성품별로_분류된_결정세번은_코드_목록으로_나눈다(wire):
    client = CLIPDetailClient()
    wire(client, _responding(_page(hs="① HSK8477.20-2000호, ②, ③ HSK8419.89-9020호\n8477.20-2000")))

    case = client.fetch_parsed(CLIPDetailRequest(doc_id="1"))

    assert case.hs_codes == ["8477202000", "8419899020"]


def test_품명만_있고_설명·결정사유가_빈_사례도_받는다(wire):
    client = CLIPDetailClient()
    wire(client, _responding(_page(description="", reason="")))

    case = client.fetch_parsed(CLIPDetailRequest(doc_id="0002000807497"))

    assert (case.product_name, case.description, case.decision_reason) == ("Skin care cosmetic (SBS-44)", "", "")
    assert case.hs_codes == ["3304991000"]


def test_없는_문서_ID는_빈_표로_오므로_오류로_알린다(wire):
    client = CLIPDetailClient()
    page = _page(hs="", enforce="", description="", reason="").replace("Skin care cosmetic (SBS-44)", "")
    wire(client, _responding(page))

    with pytest.raises(RuntimeError, match="비어 있습니다"):
        client.fetch_parsed(CLIPDetailRequest(doc_id="0000000000000"))


@pytest.mark.parametrize("doc_id", ["", "abc", "0001-988"])
def test_문서_ID는_숫자만_받는다(doc_id):
    with pytest.raises(ValidationError):
        CLIPDetailRequest(doc_id=doc_id)
