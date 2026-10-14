"""실제 모델·API 없이 어린이제품 Tool 계약을 확인한다. 품목표는 실제 법제처 응답 픽스처를 쓴다."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.schemas.children import ChildrenFact, ChildrenFacts, ChildrenReview, ChildrenSelection
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, ToolName, ToolResult, ToolStatus,
)
from app.tools.children import ChildrenTool, ChildrenToolError
from app.tools.children.search import DatabaseItemSearch, LawApiItemSearch
from app.tools.common.law import EvidenceUnavailable

from .conftest import AS_OF, FakeLaw
from app.tools.children.evidence import load_children_evidence

TOY_ROW = "conf-06"
STROLLER_ROW = "conf-13"


class _Structured:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def invoke(self, messages):
        self.owner.calls.append(self.name)
        self.owner.last_payload[self.name] = messages[-1].content
        if self.owner.error is not None:
            raise self.owner.error
        parsed = self.owner.facts if self.name == "ChildrenFacts" else self.owner.review
        return {"raw": None, "parsed": parsed, "parsing_error": None}


class Model:
    """BaseAgent가 넘기는 JSON 스키마 이름(ChildrenFacts / ChildrenReview)으로 단계를 구분하는 Fake."""

    model_name = "test-model"

    def __init__(self, facts, review=None):
        self.facts = facts
        self.review = review or ChildrenReview(selections=[])
        self.calls: list[str] = []
        self.last_payload: dict[str, str] = {}
        self.error: Exception | None = None

    def with_structured_output(self, schema, **kwargs):
        assert kwargs.get("include_raw") is True
        return _Structured(self, schema["name"])


class Search:
    """실제 픽스처 근거 위에서 조회만 세는 Fake."""

    def __init__(self, error: Exception | None = None):
        self.inner = LawApiItemSearch(lambda as_of: _EVIDENCE, as_of=AS_OF)
        self.calls: list[list[str]] = []
        self.error = error

    def catalog(self):
        if self.error is not None:
            raise self.error
        return self.inner.catalog()

    def search(self, terms, *, top_k):
        self.calls.append(list(terms))
        if self.error is not None:
            raise self.error
        return self.inner.search(terms, top_k=top_k)


_EVIDENCE = load_children_evidence(FakeLaw(), AS_OF)


def decision(selected=True):
    return ToolSelectionItem(tool_name=ToolName.CHILDREN, selected=selected, reason="어린이 연령 표기")


def product_and_facts(text="블록 장난감 세트, 사용연령 만 3세 이상",
                      values=(("product_type", "블록 장난감"), ("target_age", "만 3세 이상")),
                      search_terms=("완구",)):
    product = Product(product_id="p1", listing_text=[text])
    facts = ChildrenFacts(
        facts=[ChildrenFact(field=field, value=value, evidence_id="listing-0", quote=text) for field, value in values],
        search_terms=list(search_terms),
    )
    return product, facts


def select(item_id=TOY_ROW, **changes):
    values = dict(item_id=item_id, rationale="어린이가 놀이에 쓰는 제품으로 완구에 해당할 가능성이 있습니다.",
                  applies=True, fact_fields=["product_type"], needed_fields=[])
    values.update(changes)
    return ChildrenSelection(**values)


def review(*selections):
    return ChildrenReview(selections=list(selections))


def run(product, facts, chosen=None, search=None):
    model, search = Model(facts, chosen), search or Search()
    result = ChildrenTool(model, item_search=search).execute(product, decision())
    return result, model, search



def test_미선택이면_모델과_조회를_부르지_않는다():
    product, facts = product_and_facts()
    model, search = Model(facts), Search()
    result = ChildrenTool(model, item_search=search).execute(product, decision(False))
    assert result.status is ToolStatus.SKIPPED
    assert model.calls == [] and search.calls == []


def test_인용할_원문이_없으면_모델을_부르지_않고_정보부족이다():
    model = Model(ChildrenFacts(facts=[], search_terms=[]))
    result = ChildrenTool(model, item_search=Search()).execute(Product(product_id="p1", for_children=True), decision())
    assert model.calls == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert "제품 종류 정보가 필요합니다." in result.missing_information


def test_맞는_품목을_고르면_후보와_근거_원문과_판매_전_할_일을_낸다():
    product, facts = product_and_facts()
    result, model, search = run(product, facts, review(select()))
    assert model.calls == ["ChildrenFacts", "ChildrenReview"]
    assert search.calls[0][:2] == ["완구", "블록 장난감"]
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject == "안전확인대상 어린이제품 후보 — 완구"
    articles = [source.article for source in finding.legal_sources]
    assert articles == ["별표 2", "별표 4", "제2조 제1호"]
    assert all(not source.is_mock and source.quoted_text and source.source_url for source in finding.legal_sources)
    assert result.required_actions == [
        "[완구 · 안전확인 후보] 이 품목으로 분류되면 판매 전 KC 안전확인 신고가 된 제품인지 신고번호로 확인해야 합니다. "
        "구매대행·사입 모두 해당합니다."]
    assert result.result.certification_type == "안전확인"
    assert result.result.intended_for_children is True
    assert result.result.safety_management_required is None
    assert result.query["selected_items"] == [TOY_ROW]


def test_맞는_품목이_없어도_어린이제품이면_공급자적합성확인_후보를_낸다():
    product, facts = product_and_facts("어린이 원목 옷걸이, 만 3세 이상",
                                       (("product_type", "어린이 원목 옷걸이"), ("target_age", "만 3세 이상")),
                                       ("옷걸이",))
    result, _, _ = run(product, facts, review())
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject.startswith("공급자적합성확인대상 어린이제품 후보")
    assert [source.article for source in finding.legal_sources] == ["제2조 제1호", "제2조 제12호", "별표 3"]
    assert result.query["fallback"] == "sdoc-common"
    assert result.result.certification_type == "공급자적합성확인"


def test_연령을_모르면_공급자적합성확인으로_단정하지_않고_연령을_묻는다():
    product, facts = product_and_facts("원목 옷걸이", (("product_type", "옷걸이"),), ("옷걸이",))
    result, _, _ = run(product, facts, review())
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert "fallback" not in result.query
    assert result.missing_information == ["사용 대상 연령(예: '만 3세 이상', '36개월 미만') 정보가 필요합니다."]


def test_만_13세_이하를_포함하지_않으면_품목을_조회하지_않고_대상_아닐_가능성만_낸다():
    product, facts = product_and_facts("성인용 퍼즐 1000피스, 14세 이상",
                                       (("product_type", "퍼즐"), ("target_age", "14세 이상")))
    result, model, search = run(product, facts, review(select()))
    assert model.calls == ["ChildrenFacts"]
    assert search.calls == [[]]
    finding = result.findings[0]
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION
    assert "아닐 가능성" in finding.summary and "확정이 아닙니다" in finding.summary
    assert finding.legal_sources[0].article == "제2조 제1호"
    assert result.result.intended_for_children is False


def test_제외_물품으로_표시되면_다른_법_영역으로_안내한다():
    text = "유아용 젖병 세척 솔, 식품용 기구, 0개월 이상"
    product, facts = product_and_facts(text, (("product_type", "젖병 세척 솔"), ("target_age", "0개월 이상")))
    facts.facts.append(ChildrenFact(field="excluded_kind", value="식품용 기구", evidence_id="listing-0", quote=text))
    result, model, _ = run(product, facts, review(select()))
    assert model.calls == ["ChildrenFacts"]
    finding = result.findings[0]
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION
    assert "식품용 기구" in finding.summary and "다른 법" in finding.summary
    assert result.query["excluded_kind"] == ["식품용 기구"]


def test_정해진_이름이_아닌_제외_물품_값은_버린다():
    product, facts = product_and_facts()
    facts.facts.append(ChildrenFact(field="excluded_kind", value="장난감", evidence_id="listing-0",
                                    quote="블록 장난감 세트"))
    result, _, _ = run(product, facts, review(select()))
    assert result.query["dropped_facts"] == 1
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED



@pytest.mark.parametrize("problem", ["source", "quote", "value"])
def test_원문과_대조되지_않는_조건은_그_조건만_버린다(problem):
    product, facts = product_and_facts()
    fact = facts.facts[0]
    if problem == "source":
        fact.evidence_id = "missing"
    elif problem == "quote":
        fact.quote = "자료에 없는 문장"
    else:
        fact.value = "자료에 없는 값"
    result, _, search = run(product, facts)
    assert result.status is ToolStatus.SUCCESS
    assert result.query["dropped_facts"] == 1
    assert "제품 종류 정보가 필요합니다." in result.missing_information
    assert search.calls == [[]]


def test_연령_표기끼리_어긋나면_서로_다르다고_묻는다():
    text = "블록 장난감, 만 3세 이상, 14세 이상 권장"
    product, facts = product_and_facts(text, (("product_type", "블록 장난감"), ("target_age", "만 3세 이상"),
                                              ("target_age", "14세 이상")))
    result, _, _ = run(product, facts, review(select()))
    assert result.query["conflicted"] == ["target_age"]
    assert result.query["age_state"] is None
    assert "사용 대상 연령 정보가 서로 달라 확인이 필요합니다." in result.missing_information


@pytest.mark.parametrize("bad", [
    select("conf-99"),
    select(fact_fields=["material"]),
])
def test_대조되지_않는_선택은_버리고_비대상으로_바꾸지_않는다(bad):
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(bad))
    assert result.query["dropped_candidates"] == 1
    assert result.query["selected_items"] == []
    assert result.query["fallback"] == "sdoc-common"


def test_이유에서_해당하지_않는다고_결론_낸_선택은_후보로_내지_않는다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(
        select(), select(STROLLER_ROW, rationale="유모차로 보기 어렵습니다.", applies=False)))
    assert result.query["selected_items"] == [TOY_ROW]
    assert result.query["not_applicable"] == 1


def test_같은_행을_두_번_고르면_하나만_남긴다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select(), select()))
    assert len(result.findings) == 1
    assert result.query["dropped_candidates"] == 1


def test_품목_선택_모델에는_후보_행과_적용범위만_넘긴다():
    product, facts = product_and_facts()
    _, model, _ = run(product, facts, review(select()))
    payload = model.last_payload["ChildrenReview"]
    assert '"item_id": "conf-06"' in payload and '"scope"' in payload
    assert '"age_state": true' in payload
    assert "evidence_id" not in payload


def test_조건_추출_모델에_품목표의_품목명_목록을_준다():
    product, facts = product_and_facts()
    _, model, _ = run(product, facts, review(select()))
    payload = model.last_payload["ChildrenFacts"]
    assert '"item_names"' in payload and '"완구"' in payload and '"합성수지제어린이용품"' in payload



def test_근거_버전을_확인하지_못하면_정보부족으로_끝낸다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select()), Search(EvidenceUnavailable("버전 없음")))
    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


def test_조회_오류는_Tool_오류로_전파한다():
    product, facts = product_and_facts()
    with pytest.raises(ChildrenToolError):
        run(product, facts, review(select()), Search(RuntimeError("API 실패")))


def test_DB_조회는_아직_자리만_있다():
    with pytest.raises(NotImplementedError):
        DatabaseItemSearch(session_factory=None).search(["완구"], top_k=6)
    with pytest.raises(NotImplementedError):
        DatabaseItemSearch(session_factory=None).catalog()


def test_모델_호출_실패는_Tool_오류로_감싼다():
    product, facts = product_and_facts()
    model = Model(facts)
    model.error = TimeoutError("timeout")
    with pytest.raises(ChildrenToolError):
        ChildrenTool(model, item_search=Search()).execute(product, decision())



def _verify(product: Product, result) -> list:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.CHILDREN]
    draft = DraftAssessment(product=product, selected_tools=[ToolName.CHILDREN],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    assert verification.additional_tools_required == []
    return verification.issues


@pytest.mark.parametrize("case", ["candidate", "fallback", "adult", "missing"])
def test_결과는_Verification_규칙_검사를_통과한다(case):
    product, facts = product_and_facts()
    chosen = review(select())
    if case == "fallback":
        chosen = review()
    elif case == "adult":
        product, facts = product_and_facts("성인용 퍼즐, 14세 이상", (("product_type", "퍼즐"), ("target_age", "14세 이상")))
    elif case == "missing":
        facts.facts = facts.facts[1:]
    result, _, _ = run(product, facts, chosen)
    assert _verify(product, result) == []
