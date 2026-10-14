"""어린이제품 근거 조회·품목표 파싱을 실제 법제처 응답 픽스처로 검증한다. 실제 API는 호출하지 않는다."""

import httpx
import pytest

from app.tools.children.evidence import Scheme, load_children_evidence, parse_scope_annex
from app.tools.common.law import EvidenceUnavailable, LawLookupError, compact, join_wrapped

from .conftest import AS_OF, RULE_MST


def _item(evidence, item_id):
    return next(item for item in evidence.items if item.item_id == item_id)


def test_시행규칙_별표_1_3의_품목을_제도별로_나누고_삭제된_품목은_뺀다(children_evidence):
    by_scheme = {scheme: [item for item in children_evidence.items if item.scheme is scheme] for scheme in Scheme}
    assert len(by_scheme[Scheme.CERTIFICATION]) == 4
    assert len(by_scheme[Scheme.CONFIRMATION]) == 17
    assert len(by_scheme[Scheme.SUPPLIER]) == 14
    assert not any("삭제" in item.name for item in children_evidence.items)
    assert _item(children_evidence, "conf-06").name == "완구"
    assert _item(children_evidence, "conf-06").standards == ("어린이제품 공통안전기준", "완구 안전기준")


def test_줄바꿈으로_끊긴_품목명과_기준명을_잇는다(children_evidence):
    assert _item(children_evidence, "conf-03").name == "어린이용 스포츠 보호용품(보호 장구 및 안전모)"
    assert _item(children_evidence, "sdoc-03").name == "어린이용 안경테(선글라스를 포함한다)"
    assert "어린이용 인라인 롤러스케이트 안전기준" in _item(children_evidence, "sdoc-13").standards


def test_운용요령_적용범위를_이름이_달라도_같은_제도의_품목에_잇는다(children_evidence):
    assert children_evidence.unlinked_scopes == ()
    assert _item(children_evidence, "conf-02").scope_names == ("합성수지제어린이용품",)
    assert _item(children_evidence, "conf-05").scope_names == ("어린이용이단침대",)
    assert _item(children_evidence, "cert-01").scope_names == ("어린이용물놀이기구",)
    assert _item(children_evidence, "cert-02").scope_names == ("어린이용놀이기구",)
    assert _item(children_evidence, "conf-03").scope_names == ("보호장구", "안전모")
    assert "36 개월 미만" in " ".join(_item(children_evidence, "conf-01").scopes)


def test_근거_인용문은_칸이_섞이지_않게_품목명과_적용_안전기준으로_만든다(children_evidence):
    assert _item(children_evidence, "conf-03").row_text == (
        "3. 어린이용 스포츠 보호용품(보호 장구 및 안전모) — 적용 안전기준: "
        "어린이제품 공통안전기준, 어린이용 스포츠보호용품 안전기준")
    assert _item(children_evidence, "sdoc-03").row_text.startswith("다. 어린이용 안경테(선글라스를 포함한다) — ")
    assert children_evidence.common_standard.row_text == (
        "2. 개별 안전기준이 없는 공급자적합성확인대상어린이제품은 어린이제품 공통안전기준을 적용한다.")


def test_적용범위_원문에서_줄바꿈으로_끊긴_단어를_잇는다(children_evidence):
    scope = " ".join(_item(children_evidence, "conf-03").scopes)
    assert "인라인스케이트" in scope and "놀이시설" in scope and "명확히 규정한다" in scope
    assert "유아용의 의류" in " ".join(_item(children_evidence, "conf-01").scopes)


@pytest.mark.parametrize("fragments,expected", [
    (["보호대란, 인라인스", "케이트, 롤러"], "보호대란, 인라인스케이트, 롤러"),
    (["영·유아용의", "의류 및"], "영·유아용의 의류 및"),
    (["규정한다.", "보호대란"], "규정한다. 보호대란"),
    (["36", "개월"], "36 개월"),
    (["", "본문"], "본문"),
])
def test_칸_줄바꿈_잇기(fragments, expected):
    assert join_wrapped(fragments) == expected


def test_운용요령보다_나중에_생긴_품목은_적용범위_없이_남는다(children_evidence):
    assert _item(children_evidence, "conf-18").name == "비수면용 기울어진 요람"
    assert _item(children_evidence, "conf-18").scopes == ()


def test_법_제2조_정의와_공통안전기준_문장을_원문으로_꺼낸다(children_evidence):
    definitions = children_evidence.definitions
    assert "만 13세 이하" in definitions.children_product
    assert "식품위생법" in definitions.children_product
    assert compact(definitions.supplier_product).startswith('12."공급자적합성확인대상어린이제품"')
    common = children_evidence.common_standard
    assert common.scheme is Scheme.SUPPLIER and common.item_id == "sdoc-common"
    assert "개별 안전기준이 없는" in common.row_text


def test_기준일에_시행_중인_버전을_고르고_미래_버전은_쓰지_않는다(fake_law):
    evidence = load_children_evidence(fake_law, AS_OF)
    assert evidence.rule.version_id == RULE_MST
    assert ("get_law_text", "999999") not in fake_law.calls
    assert evidence.rule.url.endswith(RULE_MST)


def test_본문_식별_정보가_검색_결과와_다르면_근거를_쓰지_않는다(fake_law):
    fake_law.law_bodies[RULE_MST] = fake_law.law_bodies[RULE_MST].model_copy(update={"document_id": "000000"})
    with pytest.raises(EvidenceUnavailable):
        load_children_evidence(fake_law, AS_OF)


def test_별표가_없으면_근거를_쓰지_않는다(fake_law):
    body = fake_law.law_bodies[RULE_MST]
    fake_law.law_bodies[RULE_MST] = body.model_copy(update={"annexes": body.annexes[:2]})
    with pytest.raises(EvidenceUnavailable):
        load_children_evidence(fake_law, AS_OF)


def test_법제처_응답_오류는_전용_예외로_바꾸고_HTTP_오류는_그대로_올린다(fake_law):
    fake_law.error = RuntimeError("법제처 API 오류: OC=secret")
    with pytest.raises(LawLookupError) as caught:
        load_children_evidence(fake_law, AS_OF)
    assert "secret" not in str(caught.value)
    request = httpx.Request("GET", "https://www.law.go.kr/DRF/lawSearch.do")
    fake_law.error = httpx.HTTPStatusError("x", request=request, response=httpx.Response(500, request=request))
    with pytest.raises(httpx.HTTPStatusError):
        load_children_evidence(fake_law, AS_OF)


def test_가로선_사이_한_덩어리를_품목과_적용범위로_나눈다():
    text = "\n".join([
        "┌──┬──┐", "│품목│적용범위│", "├──┼──┤",
        "│갑  │첫 줄이다.│", "│제품│둘째 줄│", "├──┼──┤",
        "│스│보호│보호 설명│", "│포├──┼──┤", "│츠│모자│모자 설명│", "└──┴──┘",
    ])
    assert parse_scope_annex(text) == [("갑제품", "첫 줄이다. 둘째 줄"), ("보호", "보호 설명"), ("모자", "모자 설명")]
