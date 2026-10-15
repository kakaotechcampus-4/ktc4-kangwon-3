"""실제 모델·API 없이 식약 Tool 계약을 확인한다. 법령·품목표는 실제 법제처 응답 픽스처를 쓴다."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.schemas.food_drug import DeviceReview, DeviceSelection, FoodDrugFact, FoodDrugFacts, Judgment, Judgments
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.common.law import EvidenceUnavailable
from app.tools.food_drug import FoodDrugTool, FoodDrugToolError
from app.tools.food_drug.evidence import load_food_drug_evidence

from .conftest import AS_OF, FakeLaw

EAR_THERMOMETER = "A21010.04"     # 귀 적외선 체온계 [2]
SKIN_THERMOMETER = "A21010.05"    # 피부 적외선 체온계 [2]

_EVIDENCE = load_food_drug_evidence(FakeLaw(), AS_OF)


@pytest.fixture(autouse=True)
def no_usage_file(monkeypatch):
    monkeypatch.setattr("app.agents.base.record", lambda *a, **kw: None)


class _Structured:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def invoke(self, messages):
        self.owner.calls.append(self.name)
        self.owner.payloads[self.name] = messages[-1].content
        if self.owner.error is not None:
            raise self.owner.error
        parsed = self.owner.facts if self.name == "FoodDrugFacts" else self.owner.review
        return {"raw": None, "parsed": parsed, "parsing_error": None}


class Model:
    """BaseAgent가 넘기는 JSON 스키마 이름으로 단계를 구분하는 Fake."""

    model_name = "test-model"

    def __init__(self, facts, review=None):
        self.facts = facts
        self.review = review or DeviceReview(selections=[])
        self.calls: list[str] = []
        self.payloads: dict[str, str] = {}
        self.error: Exception | None = None

    def with_structured_output(self, schema, **kwargs):
        assert kwargs.get("include_raw") is True
        return _Structured(self, schema["name"])


def decision(selected=True):
    return ToolSelectionItem(tool_name=ToolName.FOOD_DRUG, selected=selected, reason="식품 접촉·효능 표방")


def facts_for(text, values, device_terms=(), functional_types=()):
    product = Product(product_id="p1", listing_text=[text])
    facts = FoodDrugFacts(
        facts=[FoodDrugFact(field=field, value=value, evidence_id="listing-0", quote=text) for field, value in values],
        judgments=Judgments(**{name: Judgment(answer="모름", evidence_id="", quote="")
                               for name in ("food_contact", "edible", "skin_applied")}),
        device_terms=list(device_terms), functional_types=list(functional_types),
    )
    return product, facts


SPATULA = ("실리콘 조리용 주걱, 볶음·부침 요리에 사용", (("product_type", "주걱"), ("material", "실리콘"),
                                                     ("food_contact", "예")))
THERMOMETER = ("비접촉 적외선 체온계, 이마에 대면 1초 만에 체온 측정",
               (("product_type", "적외선 체온계"), ("health_claim", "체온 측정")))


def select(item_id=EAR_THERMOMETER, **changes):
    values = dict(item_id=item_id, rationale="적외선으로 체온을 재는 기기로 체온계 품목에 해당할 가능성이 있습니다.",
                  applies=True, fact_fields=["product_type", "health_claim"], needed_fields=[])
    values.update(changes)
    return DeviceSelection(**values)


def run(product, facts, review=None, evidence=None):
    model = Model(facts, review)
    tool = FoodDrugTool(model, evidence=evidence or (lambda: _EVIDENCE))
    return tool.execute(product, decision()), model


# -- 식품용 기구·용기 --

def test_음식_접촉_인용이_있으면_식품용_기구_수입신고_후보를_낸다():
    product, facts = facts_for(*SPATULA)
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]  # 효능 문구가 없으면 의료기기 품목 선택을 부르지 않는다
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject == "식품용 기구·용기 후보 — 수입신고 대상" and "확정 아님" in finding.summary
    assert [source.article for source in finding.legal_sources] == [
        "제2조 제4호·제5호", "제14조 제1항", "제2조 제1호·제3호", "제15조 제1항", "제20조 제1항"]
    assert result.result.regulatory_categories == ["식품용 기구·용기"]
    assert result.result.ingredients_or_materials == ["실리콘"]
    assert "수입식품안전관리 특별법" in result.result.applicable_requirements


def test_식품용_기구는_사입과_구매대행의_영업등록_수입신고를_나눠_안내한다():
    product, facts = facts_for(*SPATULA)
    result, _ = run(product, facts)
    importing, buying = result.required_actions
    assert "사입·수입 판매" in importing and "수입·판매업 영업등록" in importing and "수입신고" in importing
    assert "구매대행" in buying and "인터넷 구매 대행업 영업등록" in buying and "확인이 필요합니다" in buying
    assert result.findings[0].requirements == result.required_actions


def test_재질이_없으면_기준_규격을_정하지_않았다고_남기고_묻지는_않는다():
    product, facts = facts_for("음식 담는 그릇 4개 세트", (("product_type", "그릇"), ("food_contact", "예")))
    result, _ = run(product, facts)
    assert result.missing_information == []
    assert any("재질이 확인되지 않아" in text for text in result.findings[0].assumptions)


def test_음식_접촉은_예_아니오와_원문_근거만_받는다():
    product, facts = facts_for("실리콘 조리용 주걱", (("product_type", "주걱"), ("food_contact", "조리용")))
    result, _ = run(product, facts)
    assert result.query["dropped_facts"] == 1 and result.query["food_contact"] is None
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


def test_음식_접촉_판단이_엇갈리면_묻고_후보를_내지_않는다():
    product, facts = facts_for("조리용 주걱, 식품에는 사용하지 마세요", (("product_type", "주걱"), ("food_contact", "예"),
                                                                ("food_contact", "아니오")))
    result, _ = run(product, facts)
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert len(result.missing_information) == 1 and "음식이나 음료" in result.missing_information[0]


def test_추출_단계만_음식_접촉으로_보고_원문_인용이_없으면_묻는다():
    product, facts = facts_for("원목 트레이, 거실 장식용", (("product_type", "트레이"),))
    product = product.model_copy(update={"food_contact": True})
    result, _ = run(product, facts)
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.missing_information == [
        "음식이나 음료에 직접 닿는 용도(먹을 때 쓰거나 담는 것, 조리·보관에 쓰는 것)인가요?"]


# -- 의료기기 --

def test_효능_문구가_있으면_품목표에서_고른_품목을_의료기기_후보로_낸다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, model = run(product, facts, DeviceReview(selections=[select()]))
    assert model.calls == ["FoodDrugFacts", "DeviceReview"]
    finding = result.findings[0]
    assert finding.subject == "의료기기 후보 — 귀 적외선 체온계 (2등급)"
    assert finding.determination is Determination.POSSIBLY_REQUIRED and "확정 아님" in finding.summary
    row = next(source for source in finding.legal_sources if source.article == "별표 1")
    assert row.quoted_text.startswith("A21010.04 귀 적외선 체온계 [2등급]")
    assert row.source_url.endswith("admRulSeq=2100000275656")
    assert result.query["selected_items"] == [EAR_THERMOMETER]
    assert result.result.regulatory_categories == ["의료기기"]
    assert result.result.detected_claims == ["체온 측정"]


def test_의료기기는_수입허가_판매업신고와_구매대행_제한을_안내한다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[select()]))
    importing, buying = result.required_actions
    assert "수입업허가" in importing and "판매업신고" in importing and "제26조 제1항" in importing
    assert "자가 사용용" in buying and "판매 목적으로 진열하는 것은 금지" in buying
    assert result.findings[0].requirements == result.required_actions


def test_효능_문구_칸이_비어도_품목_명칭이_있으면_원문_용도를_근거로_후보를_낸다():
    text = "비접촉 적외선 체온계, 이마에 대면 1초 만에 체온 측정"
    product, facts = facts_for(text, (("product_type", "적외선 체온계"), ("intended_use", "체온 측정")),
                               device_terms=["적외선 체온계"])
    result, model = run(product, facts, DeviceReview(selections=[select(fact_fields=["product_type", "intended_use"])]))
    assert model.calls == ["FoodDrugFacts", "DeviceReview"]
    assert result.findings[0].subject == "의료기기 후보 — 귀 적외선 체온계 (2등급)"


def test_효능_문구_없이_품목을_못_찾으면_경고하지_않고_가정으로만_남긴다():
    product, facts = facts_for("원목 안마봉, 등 두드리기용", (("product_type", "안마봉"),), device_terms=["안마기"])
    result, _ = run(product, facts)
    finding = result.findings[0]
    assert finding.subject == "식품·화장품·의료기기 해당 여부"
    assert result.required_actions == []
    assert any("의료기기 품목과 대응하지 못했습니다" in text for text in finding.assumptions)


def test_모델에는_품목표_전체가_아니라_후보_품목만_들어간다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    _, model = run(product, facts, DeviceReview(selections=[select()]))
    assert len(model.payloads["DeviceReview"]) < 6000
    assert EAR_THERMOMETER in model.payloads["DeviceReview"]


def test_맞는_품목이_없으면_비대상이_아니라_오인_광고_가능성과_함께_정보부족이다():
    product, facts = facts_for("혈액순환 개선 원적외선 팔찌, 통증 완화", (("product_type", "팔찌"), ("health_claim", "통증 완화")),
                               device_terms=["원적외선 팔찌"])
    result, _ = run(product, facts)
    finding = result.findings[0]
    assert finding.subject == "의료기기 해당 여부 — 품목 미확인"
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION and finding.risk_level is RiskLevel.MEDIUM
    assert [source.article for source in finding.legal_sources] == ["제2조 제1항", "제26조 제7항"]
    assert any("제26조 제7항" in text for text in result.required_actions)
    assert result.result.regulatory_categories == []


@pytest.mark.parametrize("bad", [
    select("Z99999.99"),
    select(fact_fields=["intended_use"]),          # 확인되지 않은 조건만 근거로 듦
])
def test_대조되지_않는_선택은_버리고_비대상으로_바꾸지_않는다(bad):
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[bad]))
    assert result.query["dropped_candidates"] == 1
    assert result.findings[0].subject == "의료기기 해당 여부 — 품목 미확인"


def test_이유에서_해당하지_않는다고_결론_낸_선택과_중복은_쓰지_않는다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    chosen = DeviceReview(selections=[select(SKIN_THERMOMETER, applies=False), select(), select()])
    result, _ = run(product, facts, chosen)
    assert result.query["not_applicable"] == 1 and result.query["dropped_candidates"] == 1
    assert result.query["selected_items"] == [EAR_THERMOMETER]


def test_품목_확정에_더_필요한_조건은_용도만_묻고_나머지는_가정으로_남긴다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[select(needed_fields=["intended_use", "material"])]))
    assert result.missing_information == ["용도 정보가 필요합니다."]
    assert any("재질 확인이 더 필요합니다" in text for text in result.findings[0].assumptions)


def test_식품용_기구와_의료기기가_함께_나올_수_있다():
    text = "적외선 체온 측정 기능 젖병, 아기 우유를 담는 실리콘 젖병"
    product, facts = facts_for(text, (("product_type", "젖병"), ("food_contact", "예"),
                                      ("health_claim", "체온 측정")), device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[select(fact_fields=["health_claim"])]))
    assert [finding.subject.split(" — ")[0] for finding in result.findings] == ["식품용 기구·용기 후보", "의료기기 후보"]
    assert result.result.regulatory_categories == ["식품용 기구·용기", "의료기기"]


# -- 식품·건강기능식품 --

JELLY = ("유산균 젤리 30포, 하루 1포 섭취, 장 건강에 도움", (("product_type", "유산균 젤리"), ("edible", "예")))


def test_먹는_상품은_식품_수입신고_후보를_낸다():
    product, facts = facts_for(*JELLY)
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]
    finding = result.findings[0]
    assert finding.subject == "식품·건강기능식품 후보 — 수입신고 대상" and "확정 아님" in finding.summary
    assert [(source.law_name, source.article) for source in finding.legal_sources][:2] == [
        ("식품위생법", "제2조 제1호"), ("수입식품안전관리 특별법", "제2조 제1호")]
    assert result.result.regulatory_categories == ["식품·건강기능식품"]
    assert any("인터넷 구매 대행업" in text for text in result.required_actions)


def test_먹는_상품의_기능성_표방은_건강기능식품_확인을_붙이고_의료기기로_보지_않는다():
    text, values = JELLY
    product, facts = facts_for(text, (*values, ("health_claim", "장 건강에 도움")), device_terms=["정장제"])
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]  # 먹는 상품은 의료기기 품목표를 조회하지 않는다
    finding = result.findings[0]
    assert "건강기능식품" in finding.summary
    assert finding.legal_sources[1].law_name == "건강기능식품에 관한 법률"
    assert any("기능성 표방" in text for text in result.required_actions)
    assert all(not item.subject.startswith("의료기기") for item in result.findings)


def test_필수_판단의_예는_원문_근거가_맞을_때만_쓴다():
    text, values = JELLY
    product, facts = facts_for(text, values[:1])
    facts.judgments.edible = Judgment(answer="예", evidence_id="listing-0", quote="하루 1포 섭취")
    facts.judgments.skin_applied = Judgment(answer="예", evidence_id="listing-0", quote="얼굴에 바르세요")  # 원문에 없음
    result, _ = run(product, facts)
    assert result.query["edible"] is True and result.query["skin_applied"] is None
    assert result.query["dropped_facts"] == 1
    assert result.result.regulatory_categories == ["식품·건강기능식품"]


def test_먹는_것인지_판단이_엇갈리면_묻는다():
    product, facts = facts_for("허브 티백, 마시지 말고 방향제로 사용", (("product_type", "티백"), ("edible", "예"),
                                                                    ("edible", "아니오")))
    result, _ = run(product, facts)
    assert result.missing_information == ["사람이 먹거나 마시는 제품인가요?"]
    assert result.result.regulatory_categories == []


# -- 화장품 --

CREAM = ("미백 기능성 수분 크림 50ml, 얼굴에 발라 사용, 전성분: 정제수, 글리세린, 나이아신아마이드",
         (("product_type", "수분 크림"), ("skin_applied", "예"), ("beauty_claim", "미백"),
          ("ingredient", "정제수"), ("ingredient", "글리세린"), ("ingredient", "나이아신아마이드")))


def test_바르는_상품은_화장품책임판매업_후보를_내고_수입대행도_안내한다():
    text, values = CREAM
    product, facts = facts_for(text, values[:2])
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]
    finding = result.findings[0]
    assert finding.subject == "화장품 후보 — 화장품책임판매업 등록 대상"
    assert [source.article for source in finding.legal_sources] == ["제2조 제1호", "제2조 제11호", "제3조 제1항~제3항"]
    importing, buying = result.required_actions
    assert "화장품책임판매업 등록" in importing and "수입대행형 거래" in buying
    assert result.result.regulatory_categories == ["화장품"]


def test_성분이_없으면_금지_원료를_대조하지_못했다고_남긴다():
    text, values = CREAM
    product, facts = facts_for(text, values[:2])
    result, _ = run(product, facts)
    assert result.query["banned_ingredients"] == []
    assert "성분 정보가 없어 사용할 수 없는 원료를 대조하지 못했습니다." in result.findings[0].assumptions


def test_기능성_표방은_시행규칙_범위에_대응될_때만_기능성화장품_후보로_낸다():
    product, facts = facts_for(*CREAM, functional_types=[1, 2, 99])
    result, _ = run(product, facts)
    functional = result.findings[1]
    assert functional.subject == "기능성화장품 후보 — 시행규칙 제2조 제1호, 시행규칙 제2조 제2호"
    assert "제99호" not in functional.rationale  # 범위에 없는 번호는 버린다
    assert [source.article for source in functional.legal_sources] == [
        "제2조 제2호", "제2조 제1호", "제2조 제2호", "제4조 제1항", "제15조 제1호~제5호"]
    assert any("심사를 받거나 보고서를 제출" in text for text in result.required_actions)
    assert result.result.regulatory_categories == ["화장품", "기능성화장품"]


def test_효과_문구가_없으면_모델이_낸_기능성_번호만으로_후보를_내지_않는다():
    text, values = CREAM
    product, facts = facts_for(text, [value for value in values if value[0] != "beauty_claim"], functional_types=[1])
    result, _ = run(product, facts)
    assert all(not finding.subject.startswith("기능성화장품") for finding in result.findings)


def test_성분이_사용할_수_없는_원료와_같으면_높은_위험으로_알린다():
    text = "수은 함유 미백 크림, 전성분: 정제수, 수은"
    product, facts = facts_for(text, (("product_type", "미백 크림"), ("skin_applied", "예"),
                                      ("ingredient", "정제수"), ("ingredient", "수은")))
    result, _ = run(product, facts)
    banned = result.findings[-1]
    assert banned.subject == "사용할 수 없는 원료 포함 가능성 — 수은 및 그 화합물"
    assert banned.determination is Determination.POSSIBLY_REQUIRED and banned.risk_level is RiskLevel.HIGH
    assert [source.article for source in banned.legal_sources] == ["제8조 제1항", "제3조", "별표 1", "제15조 제1호~제5호"]
    assert "7439-97-6" in banned.legal_sources[2].quoted_text
    assert result.query["banned_ingredients"] == ["수은 및 그 화합물"]
    assert any("제15조 제5호" in text for text in result.required_actions)


def test_금지_원료와_같은_이름이_없어도_안전하다고_하지_않는다():
    product, facts = facts_for(*CREAM)
    result, _ = run(product, facts)
    assert result.query["banned_ingredients"] == []
    assert any("안전하다는 뜻은 아닙니다" in text for text in _all_assumptions(result))


def test_바르는_상품의_질병_효능_문구는_의료기기_품목으로_보지_않는다():
    product, facts = facts_for("여드름 치료 연고형 크림, 피부에 바름", (("product_type", "크림"), ("skin_applied", "예"),
                                                                     ("health_claim", "여드름 치료")),
                               device_terms=["피부 치료기"])
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]
    assert all(not finding.subject.startswith("의료기기") for finding in result.findings)
    assert any("의약품으로 오인" in text for text in _all_assumptions(result))


def _all_assumptions(result) -> list[str]:
    return [text for finding in result.findings for text in finding.assumptions]


# -- 리뷰 지적 회귀 --

def test_조건이_붙은_금지_원료는_이름이_같아도_조건_확인으로_낮춘다():
    product, facts = facts_for("컴팩트 파우더, 전성분: 탤크, 마이카", (("product_type", "파우더"), ("skin_applied", "예"),
                                                                   ("ingredient", "탤크")))
    result, _ = run(product, facts)
    finding = result.findings[-1]
    assert finding.subject.startswith("사용할 수 없는 원료 해당 여부 확인 — ") and "탤크" in finding.subject
    assert finding.risk_level is RiskLevel.MEDIUM and "조건 해당 여부" in finding.summary
    assert any("원료 규격서" in text for text in result.required_actions)


def test_같은_금지_원료를_두_번_인용해도_판단은_하나다():
    product, facts = facts_for("크림, 전성분: 수은", (("product_type", "크림"), ("skin_applied", "예"),
                                                   ("ingredient", "수은"), ("ingredient", "수은")))
    result, _ = run(product, facts)
    assert [finding.subject for finding in result.findings].count("사용할 수 없는 원료 포함 가능성 — 수은 및 그 화합물") == 1


def test_먹는_상품의_피부_효과_문구도_건강기능식품_확인을_붙인다():
    text, values = JELLY
    product, facts = facts_for(text, (*values, ("beauty_claim", "장 건강에 도움")))
    result, _ = run(product, facts)
    assert "건강기능식품" in result.findings[0].summary
    assert any("기능성 표방" in action for action in result.required_actions)


def test_의료기기_조회의_안내는_다른_영역_판단에도_남는다():
    product, facts = facts_for("원목 안마봉 겸 국자, 국을 뜨는 데도 사용", (("product_type", "안마봉"), ("food_contact", "예")),
                               device_terms=["안마기"])
    result, _ = run(product, facts)
    food = result.findings[0]
    assert food.subject == "식품용 기구·용기 후보 — 수입신고 대상"
    assert any("의료기기 품목과 대응하지 못했습니다" in text for text in food.assumptions)


def test_버린_의료기기_선택_안내는_남은_후보_판단에_들어간다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[select("Z99999.99"), select()]))
    assert any("대조되지 않은 선택 1개" in text for text in result.findings[0].assumptions)


def test_의료기기_품목_선택이_음식_관련_칸을_요구해도_묻지_않는다():
    product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    result, _ = run(product, facts, DeviceReview(selections=[select(needed_fields=["food_contact", "edible"])]))
    assert result.missing_information == []


def test_예_판단의_근거를_원문에서_확인하지_못하면_묻는다():
    text, values = JELLY
    product, facts = facts_for(text, values[:1])
    facts.judgments.edible = Judgment(answer="예", evidence_id="listing-0", quote="없는 문장")
    result, _ = run(product, facts)
    assert result.query["edible"] is None
    assert result.missing_information == ["사람이 먹거나 마시는 제품인가요?"]


# -- 정보 부족·근거 없음·오류 --

def test_음식_접촉도_효능_문구도_없으면_비대상이_아니라_정보부족이다():
    product, facts = facts_for("면 100% 티셔츠", (("product_type", "티셔츠"),))
    result, model = run(product, facts)
    assert model.calls == ["FoodDrugFacts"]
    finding = result.findings[0]
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION and "비대상 판단이 아닙니다" in finding.summary
    assert result.required_actions == [] and result.missing_information == []


def test_원문과_대조되지_않는_조건은_그_조건만_버린다():
    product, facts = facts_for(*SPATULA)
    facts.facts.append(FoodDrugFact(field="health_claim", value="항균", evidence_id="listing-0", quote="항균 99.9%"))
    result, model = run(product, facts)
    assert result.query["dropped_facts"] == 1 and model.calls == ["FoodDrugFacts"]
    assert result.findings[0].subject == "식품용 기구·용기 후보 — 수입신고 대상"


def test_근거_법령을_확인하지_못해도_식품용_기구_후보는_내고_의료기기는_대조하지_않는다():
    def unavailable():
        raise EvidenceUnavailable("버전 없음")

    product, facts = facts_for("적외선 체온계 겸 컵, 물을 담는 컵", (("product_type", "컵"), ("food_contact", "예"),
                                                                ("health_claim", "체온")))
    result, model = run(product, facts, evidence=unavailable)
    assert model.calls == ["FoodDrugFacts"]
    food, device = result.findings
    assert food.determination is Determination.POSSIBLY_REQUIRED and food.legal_sources == []
    assert device.subject == "의료기기 해당 여부 — 품목 미확인" and device.legal_sources == []
    assert any("근거 조문 없이" in text for text in food.assumptions)


def test_근거_조회_오류는_Tool_오류다():
    def broken():
        raise ConnectionError("법제처 연결 실패")

    product, facts = facts_for(*SPATULA)
    with pytest.raises(FoodDrugToolError) as caught:
        run(product, facts, evidence=broken)
    assert isinstance(caught.value.__cause__, ConnectionError)


def test_모델_실패는_공통_Tool_예외로_알린다():
    product, facts = facts_for(*SPATULA)
    model = Model(facts)
    model.error = TimeoutError("의도한 모델 실패")
    with pytest.raises(FoodDrugToolError, match="모델 호출"):
        FoodDrugTool(model, evidence=lambda: _EVIDENCE).execute(product, decision())


def test_미선택은_모델과_조회를_호출하지_않는다():
    product, facts = facts_for(*SPATULA)
    model = Model(facts)
    result = FoodDrugTool(model).execute(product, decision(selected=False))
    assert result.status is ToolStatus.SKIPPED and model.calls == []


def test_다른_Tool의_선택정보는_실행하지_않는다():
    with pytest.raises(ValueError, match="이름"):
        FoodDrugTool().execute(Product(product_id="p1"),
                               ToolSelectionItem(tool_name=ToolName.RADIO, selected=True, reason="전파"))


# -- Verification 소비 계약 (파이프라인 연결 전) --

def _verify(product: Product, result) -> list:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.FOOD_DRUG]
    draft = DraftAssessment(product=product, selected_tools=[ToolName.FOOD_DRUG],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    assert verification.additional_tools_required == []
    return verification.issues


@pytest.mark.parametrize("case", ["food", "device", "unmatched", "none", "edible", "cosmetic", "banned"])
def test_결과는_Verification_규칙_검사를_통과한다(case):
    review = None
    if case == "food":
        product, facts = facts_for(*SPATULA)
    elif case == "device":
        product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
        review = DeviceReview(selections=[select()])
    elif case == "unmatched":
        product, facts = facts_for(*THERMOMETER, device_terms=["적외선 체온계"])
    elif case == "edible":
        product, facts = facts_for(*JELLY)
    elif case == "cosmetic":
        product, facts = facts_for(*CREAM, functional_types=[1])
    elif case == "banned":
        product, facts = facts_for("크림, 전성분: 수은", (("product_type", "크림"), ("skin_applied", "예"),
                                                       ("ingredient", "수은")))
    else:
        product, facts = facts_for("면 티셔츠", (("product_type", "티셔츠"),))
    result, _ = run(product, facts, review)
    assert _verify(product, result) == []


def test_모델_참고값에는_원문_없는_속성의_이름과_값도_들어간다():
    from app.schemas.product import Attribute
    from app.tools.food_drug.tool import _hints
    product = Product(product_id="p1", listing_text=["크림"], attributes=[Attribute(name="용량", value="50ml")])
    assert _hints(product)["attributes"] == [{"name": "용량", "value": "50ml"}]
    assert "listing_text" not in _hints(product)
