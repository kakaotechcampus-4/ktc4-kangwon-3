"""실제 모델·API 없이 전기 Tool 계약을 확인한다. 품목표는 실제 법제처 응답 픽스처를 쓴다."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.schemas.electrical import ElectricalFact, ElectricalFacts, ElectricalReview, ElectricalSelection
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, ToolName, ToolResult, ToolStatus,
)
from app.tools.electrical import ElectricalTool, ElectricalToolError
from app.tools.electrical.rules import low_voltage, normal_text
from app.tools.electrical.evidence import CachedEvidenceSource, EvidenceUnavailable, LawApiEvidenceSource
from app.tools.electrical.search import DatabaseItemSearch, LawApiItemSearch

from .conftest import AS_OF, FakeLaw

KETTLE_ROW = "cert-07-05"     # 안전인증 · 전기액체가열기기(전기주전자)
FAN_ROW = "cert-07-15"        # 안전인증 · 팬(선풍기) — 저전압 포함 비고 없음
BATTERY_ROW = "conf-10-12"    # 안전확인 · 전지(충전지) — 저전압 포함 비고 있음


class Model:
    model_name = "test-model"

    def __init__(self, facts, review=None):
        self.facts = facts
        self.review = review or ElectricalReview()
        self.calls = []

    def with_structured_output(self, schema, *, include_raw):
        assert include_raw
        self.schema = schema
        return self

    def invoke(self, messages):
        self.calls.append(self.schema)
        self.last_payload = messages[-1].content
        parsed = self.facts if self.schema is ElectricalFacts else self.review
        return {"parsed": parsed, "raw": None, "parsing_error": None}


class Search:
    """실제 품목표 픽스처 위의 조회. 호출 수와 오류 주입을 기록한다."""

    _shared = None

    def __init__(self, *, error=None):
        if Search._shared is None:
            Search._shared = LawApiItemSearch(CachedEvidenceSource(LawApiEvidenceSource(FakeLaw())), as_of=AS_OF)
        self.error = error
        self.calls = 0

    def search(self, terms, *, top_k):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return Search._shared.search(terms, top_k=top_k)


@pytest.fixture(autouse=True)
def no_usage_file(monkeypatch):
    # 테스트가 운영 사용량 로그를 변경하지 않도록 한다.
    monkeypatch.setattr("app.tools.electrical.tool.record", lambda *a, **kw: None)


def decision(selected=True):
    return ToolSelectionItem(tool_name=ToolName.ELECTRICAL, selected=selected, reason="검토 요청")


# Fake 모델이 돌려주는 조회어. 실제로는 조건 추출 LLM이 상품명을 보통 명칭으로 바꿔 낸다.
# 코드에는 상품별 동의어 사전이 없으므로, 조회가 되려면 이 값이 필요하다.
FAKE_SEARCH_TERMS = {"전기포트": ["전기주전자"], "보조배터리": ["전지", "리튬이차전지"]}


def product_and_facts(text="스테인리스 전기포트, AC 220V 60Hz 전용",
                      values=(("product_type", "전기포트"), ("power_source", "AC"), ("rated_voltage", "220V")),
                      search_terms=None):
    product = Product(product_id="p1", listing_text=[text])
    product_type = next((value for field, value in values if field == "product_type"), "")
    facts = ElectricalFacts(
        facts=[ElectricalFact(field=field, value=value, evidence_id="listing-0", quote=text) for field, value in values],
        search_terms=search_terms if search_terms is not None else FAKE_SEARCH_TERMS.get(product_type, []),
    )
    return product, facts


def test_상품별_동의어_사전_없이_조회어가_없으면_정답_행을_못_찾을_수_있다():
    # 동의어를 코드에 하드코딩하지 않았다는 확인. 조회어가 없으면 "전기포트"로는 전기주전자 행이 잘 안 잡힌다.
    product, facts = product_and_facts(search_terms=[])
    _, _, search = run(product, facts, review())
    found = Search._shared.search(["전기포트", "AC"], top_k=8)
    assert KETTLE_ROW not in [block.block_id for block in found.blocks]
    found = Search._shared.search(["전기주전자"], top_k=8)
    assert [block.block_id for block in found.blocks][0] == KETTLE_ROW


def select(item_id=KETTLE_ROW, **changes):
    values = dict(item_id=item_id, rationale="물을 끓이는 교류 가전으로 전기주전자에 해당할 가능성이 있습니다.",
                  fact_fields=["product_type"])
    values.update(changes)
    return ElectricalSelection(**values)


def review(*selections):
    return ElectricalReview(selections=list(selections))


def run(product, facts, chosen=None, search=None):
    model, search = Model(facts, chosen), search or Search()
    result = ElectricalTool(model, item_search=search).execute(product, decision())
    return result, model, search


# -- 정상 경로 --

def test_조회한_후보_행에서_고른_품목을_후보로_내고_근거는_행_원문이다():
    product, facts = product_and_facts()
    result, model, search = run(product, facts, review(select()))

    assert result.status is ToolStatus.SUCCESS
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject.startswith("안전인증대상 후보")
    assert "전기주전자" in finding.legal_sources[0].quoted_text
    assert "OC=" not in finding.legal_sources[0].source_url
    assert finding.legal_sources[0].is_mock is False
    assert result.result.safety_management_required is None
    assert result.result.legal_sources == []
    assert result.query["selected_items"] == [KETTLE_ROW]
    assert KETTLE_ROW in result.query["candidate_items"]
    assert result.query["low_voltage"] is False
    assert model.calls == [ElectricalFacts, ElectricalReview]
    assert search.calls == 1


def test_모델에는_법령_전체가_아니라_후보_행만_들어간다():
    product, facts = product_and_facts()
    _, model, _ = run(product, facts, review(select()))
    # 후보 8행 + 상품 조건. 법령 전체(약 10만 자)가 들어가지 않는다.
    assert len(model.last_payload) < 8000
    assert "전기주전자" in model.last_payload


def test_전압이_없어도_품목_검토는_하고_전압을_질문으로_남긴다():
    product, facts = product_and_facts("USB 충전식 휴대용 미니 선풍기",
                                       (("product_type", "휴대용 미니 선풍기"), ("power_source", "USB 충전식")))
    result, model, _ = run(product, facts, review(select(FAN_ROW, rationale="선풍기 품목입니다. 전압 확인 필요.")))

    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED
    assert "정격 전압 정보가 필요합니다." in result.missing_information
    assert result.query["low_voltage"] is None
    assert model.calls == [ElectricalFacts, ElectricalReview]


# -- 입력·조건 --

def test_미선택은_모델과_조회를_호출하지_않는다():
    product, facts = product_and_facts()
    model, search = Model(facts), Search()
    result = ElectricalTool(model, item_search=search).execute(product, decision(False))
    assert result.status is ToolStatus.SKIPPED
    assert model.calls == [] and search.calls == 0


def test_boolean만_있으면_조건을_추측하지_않는다():
    result = ElectricalTool().execute(Product(product_id="p1", electrical_powered=True), decision())
    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert len(result.missing_information) == 3


def test_제품_종류가_없으면_조회하지_않는다():
    product, facts = product_and_facts(values=(("power_source", "AC"), ("rated_voltage", "220V")))
    result, model, search = run(product, facts)
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert "제품 종류 정보가 필요합니다." in result.missing_information
    assert model.calls == [ElectricalFacts] and search.calls == 0


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
    assert result.missing_information == ["제품 종류 정보가 필요합니다."]
    assert result.query["dropped_facts"] == 1
    assert search.calls == 0


def test_서로_다른_전압은_하나를_고르지_않고_저전압도_판정하지_않는다():
    product, facts = product_and_facts()
    product.listing_text.append("정격 110V")
    facts.facts.append(ElectricalFact(field="rated_voltage", value="110V", evidence_id="listing-1", quote="정격 110V"))
    result, _, _ = run(product, facts, review(select()))
    assert "정격 전압 정보가 필요합니다." in result.missing_information
    assert result.query["low_voltage"] is None


# -- 선택 검증 --

@pytest.mark.parametrize("bad", [
    select("cert-99-99"),                              # 후보에 없는 행
    select(fact_fields=["rated_power"]),               # 확인되지 않은 조건 참조
])
def test_대조되지_않는_선택은_버리고_비대상으로_바꾸지_않는다(bad):
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(bad))
    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.query["dropped_candidates"] == 1


def test_확인된_조건이_하나라도_있으면_미확인_조건만_빼고_선택을_남긴다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select(fact_fields=["product_type", "intended_use"])))
    assert result.query["selected_items"] == [KETTLE_ROW]
    assert all(not fact.startswith("제품 용도") for fact in result.findings[0].product_facts_used)


def test_같은_행을_두_번_고르면_하나만_남긴다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select(), select()))
    assert len(result.findings) == 1
    assert result.query["dropped_candidates"] == 1


def test_빈_선택은_비대상이_아니라_정보부족이다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review())
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.result.safety_management_required is None


def test_맞는_품목도_전기_조건도_없으면_전압을_묻지_않는다():
    product, facts = product_and_facts("내열 실리콘 주걱", (("product_type", "실리콘 주걱"),))
    result, _, _ = run(product, facts, review())
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.missing_information == []


def test_전기_조건이_있으면_맞는_품목이_없어도_빠진_전압을_묻는다():
    product, facts = product_and_facts("USB 충전식 미니 가습기",
                                       (("product_type", "미니 가습기"), ("power_source", "USB 충전식")))
    result, _, _ = run(product, facts, review())
    assert result.missing_information == ["정격 전압 정보가 필요합니다."]


# -- 저전압 규칙 (운용요령 제3조) --

@pytest.mark.parametrize("values,expected", [
    ((("power_source", "AC"), ("rated_voltage", "220V")), (False, "AC")),
    ((("power_source", "AC"), ("rated_voltage", "24V")), (True, "AC")),
    ((("rated_voltage", "DC 12V"),), (True, "DC")),
    ((("rated_voltage", "DC 48V"),), (False, "DC")),
    ((("power_source", "USB"), ("rated_voltage", "5V")), (True, "DC")),
    ((("rated_voltage", "220V"),), (None, None)),          # 교류·직류 불명
    ((("power_source", "AC"),), (None, "AC")),              # 전압 없음
])
def test_저전압은_명시된_전류_종류와_전압으로만_판정한다(values, expected):
    by_field = {}
    for field, value in values:
        by_field.setdefault(field, []).append(
            ElectricalFact(field=field, value=value, evidence_id="listing-0", quote=value))
    assert low_voltage(by_field) == expected


def test_저전압_제품이_저전압_포함_비고가_없는_행을_고르면_규칙이_버린다():
    product, facts = product_and_facts("USB 선풍기 DC 5V",
                                       (("product_type", "USB 선풍기"), ("rated_voltage", "DC 5V")))
    result, model, _ = run(product, facts, review(select(FAN_ROW)))
    assert result.query["low_voltage"] is True
    assert result.query["dropped_candidates"] == 1
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert '"low_voltage_excluded": true' in model.last_payload


def test_저전압이어도_비고가_저전압을_포함하는_행은_후보로_남고_제3조를_근거에_붙인다():
    product, facts = product_and_facts("리튬폴리머 보조배터리, 출력 DC 5V",
                                       (("product_type", "보조배터리"), ("rated_voltage", "DC 5V")))
    result, _, search = run(product, facts, review(select(BATTERY_ROW)))
    assert BATTERY_ROW in result.query["candidate_items"]
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject.startswith("안전확인대상 후보")
    assert "제3조" in [source.article for source in finding.legal_sources]


# -- 전지 전용 구조 제외 (운용요령 별표 공통 비고) --

def test_전지로만_동작하면_본체_행은_빼고_전지_행만_남긴다():
    product, facts = product_and_facts(
        "충전식 무선 미니 선풍기, 내장 배터리로만 작동",
        (("product_type", "미니 선풍기"), ("power_source", "내장 배터리"), ("battery_only", "예")))
    result, model, _ = run(product, facts, review(select(FAN_ROW)))
    assert FAN_ROW in result.query["battery_only_excluded"]
    assert FAN_ROW not in model.last_payload.split('"candidates"')[1]
    assert result.query["dropped_candidates"] == 1
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert any("공통 비고" in item for item in result.findings[0].assumptions)
    # 본체 대신 검토할 내장 전지 행을 따로 조회해 후보에 넣는다.
    assert BATTERY_ROW in model.last_payload


def test_전지_전용_제품은_내장_전지_행을_후보로_고를_수_있다():
    product, facts = product_and_facts(
        "무선 핸디 청소기, 내장 배터리로만 작동",
        (("product_type", "무선 핸디 청소기"), ("battery_only", "예")))
    result, _, _ = run(product, facts, review(select(BATTERY_ROW)))
    assert result.query["selected_items"] == [BATTERY_ROW]
    assert result.findings[0].subject.startswith("안전확인대상 후보 — 전지")


def test_전지_사용이_보이는데_전지_전용인지_모르면_본체_후보에_제외_가능성을_붙이고_묻는다():
    product, facts = product_and_facts("USB 충전식 휴대용 미니 선풍기",
                                       (("product_type", "휴대용 미니 선풍기"), ("power_source", "USB 충전식")))
    result, model, _ = run(product, facts, review(select(FAN_ROW)))
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert any("전지(건전지·충전지)만으로 동작하는 구조라면" in item for item in finding.assumptions)
    assert any("공통 비고" in (source.article or "") for source in finding.legal_sources)
    assert any("건전지·충전지로만 동작" in question for question in result.missing_information)
    assert '"common_notes"' in model.last_payload


def test_전지_전용_여부는_예_아니오와_원문_근거만_받는다():
    product, facts = product_and_facts(values=(("product_type", "전기포트"), ("battery_only", "전지 전용")))
    result, _, _ = run(product, facts, review(select()))
    assert result.query["dropped_facts"] == 1
    assert result.query["battery_only"] is None


# -- 구매대행 특례 (법 제35조, 시행규칙 별표 13) --

def test_구매대행_특례_품목이면_구매대행과_사입의_할_일을_나눠_안내한다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select()))
    assert result.query["purchase_agent"] == {KETTLE_ROW: "listed"}
    assert "KC 표시 없이 가능" in result.findings[0].summary
    assert any(action.startswith("[전기액체 가열기기 · 안전인증 후보] 구매대행:") for action in result.required_actions)
    assert any("사입·수입 판매" in action for action in result.required_actions)
    assert any((source.article or "").startswith("별표 13") for source in result.findings[0].legal_sources)


def test_특례_목록에서_이름을_못_찾으면_특례_없음으로_확정하지_않는다():
    product, facts = product_and_facts("리튬폴리머 보조배터리, 출력 DC 5V",
                                       (("product_type", "보조배터리"), ("rated_voltage", "DC 5V")))
    result, _, _ = run(product, facts, review(select(BATTERY_ROW)))
    assert result.query["purchase_agent"] == {BATTERY_ROW: "unmatched"}
    assert "확인이 필요합니다" in result.findings[0].summary
    assert any("확인하기 전까지는 KC 안전확인 신고를 받은 제품만" in action for action in result.required_actions)
    assert not any("구매대행·사입 모두" in action for action in result.required_actions)


def test_제외_조건이_붙은_특례는_조건부로만_안내한다():
    product, facts = product_and_facts("스마트폰용 고속 충전기, 입력 AC 100-240V",
                                       (("product_type", "고속 충전기"), ("power_source", "AC")),
                                       search_terms=["직류전원장치"])
    result, _, _ = run(product, facts, review(select("cert-10-01")))
    assert result.query["purchase_agent"] == {"cert-10-01": "listed_with_exclusion"}
    assert not any("KC 표시 없이 구매대행할 수 있습니다" in action for action in result.required_actions)
    assert any("제외 조건" in action and "해당하지 않으면" in action for action in result.required_actions)
    assert "해당하지 않으면" in result.findings[0].summary


def test_구매대행_특례_목록을_확인하지_못해도_품목_판단은_계속한다():
    from app.tools.electrical.search import ItemCandidates

    class NoAnnex13(Search):
        def search(self, terms, *, top_k):
            found = super().search(terms, top_k=top_k)
            return ItemCandidates(found.blocks, found.rule_scope, found.notice_scope, found.documents,
                                  common_notes=found.common_notes, purchase_agent={})

    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select()), search=NoAnnex13())
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED
    assert result.query["purchase_agent"] == {KETTLE_ROW: "unknown"}
    assert result.required_actions == ["[전기액체 가열기기 · 안전인증 후보] 판매 전 KC 안전인증 여부를 확인해야 합니다."]


ESS_ROW = "cert-12-01"        # 안전인증 · 전기저장장치구성품 리튬이차단전지


def test_전기저장장치_용도가_없으면_ESS_구성품_행은_후보에서_뺀다():
    product, facts = product_and_facts("리튬폴리머 보조배터리, 출력 DC 5V",
                                       (("product_type", "보조배터리"), ("rated_voltage", "DC 5V")))
    result, model, _ = run(product, facts, review(select(ESS_ROW), select(BATTERY_ROW)))
    assert ESS_ROW in result.query["filtered_items"]
    assert ESS_ROW not in model.last_payload
    assert result.query["selected_items"] == [BATTERY_ROW]
    assert result.query["dropped_candidates"] == 1


def test_전기저장장치_용도가_있으면_ESS_구성품_행을_남긴다():
    product, facts = product_and_facts("가정용 전기저장장치 리튬이차전지 모듈 DC 48V",
                                       (("product_type", "전기저장장치 리튬이차전지 모듈"), ("rated_voltage", "DC 48V")))
    result, model, _ = run(product, facts, review(select(ESS_ROW)))
    assert ESS_ROW not in result.query["filtered_items"]
    assert result.query["selected_items"] == [ESS_ROW]


# -- 조회·모델 실패 --

def test_품목표를_확인할_수_없으면_정보부족이다():
    product, facts = product_and_facts()
    result, model, _ = run(product, facts, search=Search(error=EvidenceUnavailable("버전 불명")))
    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert model.calls == [ElectricalFacts]


def test_조회_오류는_비대상이나_정보부족으로_바꾸지_않는다():
    product, facts = product_and_facts()
    with pytest.raises(ElectricalToolError) as caught:
        run(product, facts, search=Search(error=RuntimeError("API 실패")))
    assert isinstance(caught.value.__cause__, RuntimeError)


@pytest.mark.parametrize("mode", ["call", "parse", "missing_output"])
def test_모델_호출과_파싱_실패는_공통_Tool_예외로_알린다(mode):
    product, facts = product_and_facts()

    class BrokenModel(Model):
        def invoke(self, messages):
            if mode == "call":
                raise TimeoutError("의도한 모델 실패")
            return {"raw": None, "parsed": None,
                    "parsing_error": ValueError("파싱 실패") if mode == "parse" else None}

    with pytest.raises(ElectricalToolError, match="모델 처리"):
        ElectricalTool(BrokenModel(facts), item_search=Search()).execute(product, decision())


def test_다른_Tool의_선택정보는_실행하지_않는다():
    with pytest.raises(ValueError, match="이름"):
        ElectricalTool().execute(Product(product_id="p1"),
                                 ToolSelectionItem(tool_name=ToolName.RADIO, selected=True, reason="전파"))


def test_DB_조회는_아직_스텁이다():
    with pytest.raises(NotImplementedError):
        DatabaseItemSearch(session_factory=None).search(["전기포트"], top_k=8)


def test_표_테두리와_공백을_무시하고_대조한다():
    assert normal_text("│비고) 정격입력이    │\n│것은 제외한다. │") == normal_text("비고) 정격입력이 것은 제외한다.")


# -- Verification 소비 계약 (파이프라인 연결 전) --

def _verify(product: Product, result) -> list:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.ELECTRICAL]
    draft = DraftAssessment(product=product, selected_tools=[ToolName.ELECTRICAL],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    assert verification.additional_tools_required == []
    return verification.issues


@pytest.mark.parametrize("case", ["candidate", "missing", "dropped", "low_voltage"])
def test_결과는_Verification_규칙_검사를_통과한다(case):
    product, facts = product_and_facts()
    chosen = review(select())
    if case == "missing":
        facts.facts = facts.facts[1:]
    elif case == "dropped":
        chosen = review(select("cert-99-99"))
    elif case == "low_voltage":
        product, facts = product_and_facts("리튬폴리머 보조배터리, 출력 DC 5V",
                                           (("product_type", "보조배터리"), ("rated_voltage", "DC 5V")))
        chosen = review(select(BATTERY_ROW))
    result, _, _ = run(product, facts, chosen)
    assert _verify(product, result) == []
