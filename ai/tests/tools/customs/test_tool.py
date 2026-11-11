"""실제 모델·API 없이 통관 Tool 계약을 확인한다. 법령·결정사례는 실제 응답 픽스처를 쓴다."""

import httpx
import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.tools.customs.schemas import CustomsFact, CustomsFacts, CustomsReview, CustomsSelection
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.common.law import EvidenceUnavailable
from app.tools.common.questions import ANSWER_PREFIX
from app.tools.customs import CustomsTool, CustomsToolError
from app.tools.customs.evidence import load_customs_evidence
from app.tools.customs.search import CaseCandidates, ClipCaseSearch, HsCase, Requirement

from .conftest import AS_OF, FakeClip, FakeLaw, FakeRequirements

KETTLE_CASE = "0072016001137"    # 8516.79-9000 ELECTRIC KETTLE(MEK-J12)
JUG_CASE = "0072018002192"       # 8516.79-9000 Cordless Jug Kettle
COFFEE_CASE = "0072017001538"    # 8419.81-0000 커피 머신(다른 물품)
SPATULA_CASE = "0072017003150"   # 3924.10-0000 실리콘 주걱

_EVIDENCE = load_customs_evidence(FakeLaw(), AS_OF)


@pytest.fixture(autouse=True)
def no_usage_file(monkeypatch):
    monkeypatch.setattr("app.observability.usage.record", lambda *a, **kw: None)


class _Structured:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def invoke(self, messages):
        self.owner.calls.append(self.name)
        self.owner.payloads[self.name] = messages[-1].content
        if self.owner.error is not None:
            raise self.owner.error
        parsed = self.owner.facts if self.name == "CustomsFacts" else self.owner.review
        return {"raw": None, "parsed": parsed, "parsing_error": None}


class Model:
    """BaseAgent가 넘기는 JSON 스키마 이름으로 단계를 구분하는 Fake."""

    model_name = "test-model"

    def __init__(self, facts, review=None):
        self.facts = facts
        self.review = review or CustomsReview(selections=[])
        self.calls: list[str] = []
        self.payloads: dict[str, str] = {}
        self.error: Exception | None = None

    def with_structured_output(self, schema, **kwargs):
        assert kwargs.get("include_raw") is True
        return _Structured(self, schema["name"])


def decision(selected=True):
    return ToolSelectionItem(tool_name=ToolName.CUSTOMS, selected=selected, reason="수입 상품")


def product_and_facts(text="스테인리스 무선 전기주전자 1.7L, 전기로 물을 끓임",
                      values=(("product_type", "전기주전자"), ("material", "스테인리스"), ("function", "전기로 물을 끓임")),
                      search_terms=("전기주전자", "전기포트")):
    product = Product(product_id="p1", listing_text=[text])
    facts = CustomsFacts(
        facts=[CustomsFact(field=field, value=value, evidence_id="listing-0", quote=text) for field, value in values],
        search_terms=list(search_terms),
    )
    return product, facts


def select(case_id=KETTLE_CASE, **changes):
    values = dict(case_id=case_id, rationale="전기로 물을 끓이는 주전자로 같은 물품입니다.", applies=True,
                  fact_fields=["product_type", "function"], needed_fields=[])
    values.update(changes)
    return CustomsSelection(**values)


def review(*selections):
    return CustomsReview(selections=list(selections))


def run(product, facts, chosen=None, *, requirements=None, evidence=None, clip_errors=None):
    model = Model(facts, chosen)
    calls: list[str] = []
    requirements = requirements or FakeRequirements()
    tool = CustomsTool(model, case_search=ClipCaseSearch(lambda: FakeClip(calls, clip_errors or {})),
                       requirements=requirements, evidence=evidence or (lambda: _EVIDENCE))
    return tool.execute(product, decision()), model, calls, requirements


def bare_tool(model=None):
    """조회까지 가지 않는 테스트용. 조회 객체는 가짜."""
    return CustomsTool(model, case_search=ClipCaseSearch(lambda: FakeClip([], {})),
                       requirements=FakeRequirements(), evidence=lambda: _EVIDENCE)


# -- 정상 경로 --

def test_결정사례로_HS_후보를_찾고_그_HS의_세관장확인_요건을_후보로_낸다():
    product, facts = product_and_facts()
    result, model, calls, requirements = run(product, facts, review(select()))

    assert result.status is ToolStatus.SUCCESS
    assert model.calls == ["CustomsFacts", "CustomsReview"]
    assert sorted(calls) == ["전기주전자", "전기포트"]
    assert requirements.calls == ["8516799000"]
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject == "세관 확인 서류가 필요할 수 있음 — 전기용품 및 생활용품 안전관리법"
    # 본문은 할 일 문구와 같은 말로 품목번호와 서류를 줄마다 적음. 서류는 근거로 인용하는 고시 별표 2 구비요건 문구를
    # 대상(가)(나)(다)마다 짝지어 안내 (GW 서류명 "전기용품 및 생활용품 요건확인서"가 아님)
    assert finding.summary == (
        "- 품목번호: HS 8516.79-9000 후보\n- 미리 갖출 서류: 물품에 따라 아래 중 해당하는 서류: "
        "안전인증대상 제품: 전기용품 및 생활용품 세관장 확인물품 확인증 / "
        "안전확인대상 제품: 전기용품 및 생활용품 세관장 확인물품 확인증 / "
        "공급자 적합성 확인대상 제품: 공급자적합성 확인신고 확인증명서(단,전기용품에 한함)")
    assert result.result.hs_code_candidates == ["8516.79-9000"]
    assert result.result.applicable_requirements == ["전기용품 및 생활용품 안전관리법"]
    assert result.query["selected_cases"] == [KETTLE_CASE]
    assert result.query["related_tools"] == {"전기용품 및 생활용품 안전관리법": ToolName.ELECTRICAL.value}


def test_고른_결정사례가_여럿이면_사례마다_이유를_줄을_나눠_남긴다():
    product, facts = product_and_facts()
    chosen = review(select(), select(JUG_CASE, rationale="무선 주전자로 같은 물품입니다."))

    result, _, _, _ = run(product, facts, chosen)

    assert result.findings[0].rationale == "전기로 물을 끓이는 주전자로 같은 물품입니다.\n무선 주전자로 같은 물품입니다."
    # 요약도 품목번호와 서류를 줄을 나눔
    assert "후보\n- 미리 갖출 서류: " in result.findings[0].summary


def test_근거는_관세법_제226조와_고시_별표2_행과_결정사례다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()))
    sources = result.findings[0].legal_sources
    articles = [source.article for source in sources]
    assert articles[:2] == ["제226조", "별표 2 (9)"]
    assert "제7조" in articles and "제19조" in articles
    case = sources[-1]
    assert case.source_name == "관세청 품목분류 결정사례(CLIP)" and KETTLE_CASE in case.article
    assert case.source_url is None and case.is_mock is False
    assert all(source.source_name == "법제처 국가법령정보" for source in sources[:-1])
    assert all("OC=" not in (source.source_url or "") for source in sources)


def test_생략_제외_법령은_구매대행도_해당한다고_한_건으로_안내한다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()))
    [action] = result.required_actions
    assert "세관에 아래 서류를 내야 할 수 있습니다." in action and "공급자적합성 확인신고 확인증명서(단,전기용품에 한함)" in action
    assert action.split("\n")[-1] == "- 구매대행도 해당"
    # 재실행에서 이 판단이 빠지면 ToolExecutor가 이 판단의 할 일만 지울 수 있다.
    assert set(result.findings[0].requirements) == set(result.required_actions)


def test_생략_제외가_아닌_법령은_구매대행이면_생략될_수_있다고_안내한다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()),
                          requirements=FakeRequirements({"8516799000": [FakeRequirements.RADIO]}))
    [action] = result.required_actions
    assert action.split("\n")[-1] == "- 구매대행: 구매자 개인이 쓰려고 들여오는 경우 등에는 생략될 수 있음"
    assert result.query["related_tools"] == {"전파법": ToolName.RADIO.value}


def test_야생생물법_요건에는_판단_요약과_할_일에_멸종위기종_조건을_덧붙인다():
    product, facts = product_and_facts()
    cites = Requirement(hs_code="8516799000", law_name="야생생물 보호 및 관리에 관한 법률(허가)",
                        agency="유역(지방)환경청", document="국제적멸종위기 동식물 수입허가서")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [cites]}))
    [finding] = result.findings
    assert "소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다." in finding.summary
    assert finding.summary.split("\n") == [
        "- 품목번호: HS 8516.79-9000 후보",
        # 고시 구비요건 문구. 삭제된 항목("< 삭 제 >")은 뺌
        "- 미리 갖출 서류: 물품에 따라 아래 중 해당하는 서류: 유역(지방)환경청장의 멸종위기 야생생물 (국제적 멸종위기종) "
        "수입허가증(서) / 국립야생동물질병관리원장의 야생동물 수입검역 증명서",
        "- 악어·뱀 등 멸종위기종(CITES) 가죽이나 부위를 쓴 제품에만 해당하고, 소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다."]
    assert result.required_actions[0].endswith("소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다.")
    # 재질(스테인리스)을 이미 알면 소재로 빠질 요건이 남아도 재질을 다시 묻지 않음
    assert result.missing_information == []


def test_같은_HS의_요건이_여러_법령이면_법령마다_판단을_낸다():
    product, facts = product_and_facts()
    table = {"8516799000": [FakeRequirements.ELECTRICAL, FakeRequirements.RADIO]}
    result, _, _, _ = run(product, facts, review(select(), select(JUG_CASE)), requirements=FakeRequirements(table))
    assert [finding.subject.split(" — ")[1] for finding in result.findings] == [
        "전기용품 및 생활용품 안전관리법", "전파법"]
    assert result.query["hs_candidates"] == ["8516799000"]  # 같은 HS의 두 사례는 한 번만 조회
    assert len(result.query["selected_cases"]) == 2


def test_모델에는_후보_사례의_앞부분만_들어간다():
    product, facts = product_and_facts()
    _, model, _, _ = run(product, facts, review(select()))
    assert len(model.payloads["CustomsReview"]) < 12000
    assert KETTLE_CASE in model.payloads["CustomsReview"]


# -- 요건이 없거나 확인하지 못한 경우 --

def test_조회해서_요건이_없으면_정보부족이_아니라_세관_확인_서류_필요_없음으로_낸다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({}))
    finding = result.findings[0]
    assert finding.subject == "세관 확인 서류 필요 없음"
    assert finding.determination is Determination.NOT_REQUIRED
    assert finding.risk_level is RiskLevel.LOW
    # 화면에 나가는 요약은 품목번호만. 국내 판매 규제 안내는 화면에 안 나가는 가정에 남김
    assert finding.summary == "품목번호: HS 8516.79-9000 후보"
    assert any("국내 판매 규제" in note and "없다는 뜻은 아닙니다" in note for note in finding.assumptions)
    assert any("다른 HS로 분류되면" in note for note in finding.assumptions)
    # 확정 판단이라 인용문과 공개 주소가 있는 근거 조문을 붙인다(관세법 제226조)
    assert any(source.quoted_text and source.source_url for source in finding.legal_sources)
    assert result.required_actions == []


def test_근거_법령을_읽지_못하면_요건이_없어도_정보부족으로_둔다():
    def unavailable():
        raise EvidenceUnavailable("관세법 본문 시행일 확인 실패")
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({}), evidence=unavailable)
    finding = result.findings[0]
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION
    assert finding.subject == "세관장확인 대상 법령 — 조회되지 않음"


def test_세관장확인_필요_칸은_모든_후보를_조회해_요건이_없을_때만_false다():
    # #797: 판단은 "필요 없음"인데 칸이 비어(null) 검증이 "확인 결과 없이 확정"으로 오해하던 것
    product, facts = product_and_facts()
    none, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({}))
    assert none.result.customs_confirmation_required is False
    # 요건이 남으면 HS가 후보라 확정하지 않음
    some, _, _, _ = run(product, facts, review(select()))
    assert some.result.customs_confirmation_required is None
    # 조회하지 못한 후보가 있으면 모름
    missing = FakeRequirements(error=EvidenceUnavailable("세관장확인 GW 서비스 키(DATA_GO_KR_KEY)가 없어 요건을 조회하지 못했습니다."))
    unresolved, _, _, _ = run(product, facts, review(select()), requirements=missing)
    assert unresolved.result.customs_confirmation_required is None


def test_근거_법령을_읽지_못해_정보부족이면_요건이_없어도_세관장확인_필요_칸을_비운다():
    def unavailable():
        raise EvidenceUnavailable("관세법 본문 시행일 확인 실패")
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({}), evidence=unavailable)
    assert result.result.customs_confirmation_required is None


def test_GW가_요건_종류를_붙인_같은_법령은_판단_하나로_묶는다():
    from dataclasses import replace
    permit = replace(FakeRequirements.ELECTRICAL, law_name="전기용품 및 생활용품 안전관리법(허가)", agency="한국제품안전협회")
    product, facts = product_and_facts()
    table = {"8516799000": [FakeRequirements.ELECTRICAL, permit]}
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements(table))
    candidates = [finding for finding in result.findings if finding.subject.startswith("세관 확인 서류가 필요할 수 있음")]
    assert len(candidates) == 1
    assert candidates[0].subject == "세관 확인 서류가 필요할 수 있음 — 전기용품 및 생활용품 안전관리법"


def test_GW_키가_없으면_요건_미확인으로_내고_확인_방법을_안내한다():
    product, facts = product_and_facts()
    missing_key = FakeRequirements(error=EvidenceUnavailable("세관장확인 GW 서비스 키(DATA_GO_KR_KEY)가 없어 요건을 조회하지 못했습니다."))
    result, _, _, _ = run(product, facts, review(select()), requirements=missing_key)
    finding = result.findings[0]
    assert finding.subject == "세관 확인 서류 — 조회하지 못함"
    assert finding.summary == ("- 품목번호: HS 8516.79-9000 후보\n"
                               "- 필요한 서류를 조회하지 못했습니다. 관세사나 세관에 직접 확인이 필요합니다.")
    assert finding.determination is Determination.INSUFFICIENT_INFORMATION
    assert result.result.hs_code_candidates == ["8516.79-9000"]
    assert any("UNI-PASS" in text for text in result.required_actions)
    assert any("DATA_GO_KR_KEY" in text for text in finding.assumptions)


def test_6단위_HS는_요건을_조회하지_않고_미확인으로_남긴다(monkeypatch):
    product, facts = product_and_facts()
    case = FakeClip.responses["전기주전자"].items[3]
    monkeypatch.setitem(FakeClip.responses, "전기주전자", FakeClip.responses["전기주전자"].model_copy(update={
        "items": [case.model_copy(update={"hs_codes": ["851679"]})]}))
    result, _, _, requirements = run(product, facts, review(select()))
    assert requirements.calls == []
    assert result.query["hs_candidates"] == ["851679"]
    assert result.findings[0].subject == "세관 확인 서류 — 조회하지 못함"
    assert result.result.hs_code_candidates == ["8516.79"]


def test_근거_법령을_확인하지_못해도_요건_후보는_내고_생략_여부는_확인_필요로_둔다():
    product, facts = product_and_facts()

    def unavailable():
        raise EvidenceUnavailable("버전 없음")

    result, _, _, _ = run(product, facts, review(select()), evidence=unavailable)
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert [source.source_name for source in finding.legal_sources] == ["관세청 품목분류 결정사례(CLIP)"]
    assert any("- 구매대행: 생략 여부를 확인하지 못함" in text for text in result.required_actions)


# -- 정보 부족·대조 실패 --

def test_제품_종류가_없으면_조회하지_않는다():
    product, facts = product_and_facts(values=(("material", "스테인리스"),))
    result, model, calls, _ = run(product, facts)
    assert model.calls == ["CustomsFacts"] and calls == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.missing_information == ["어떤 제품인지(제품 종류) 확인이 필요합니다."]


def test_비슷한_결정사례가_없으면_선택_모델을_부르지_않고_정보부족이다():
    product, facts = product_and_facts(values=(("product_type", "주전자"),), search_terms=("없는 검색어",))
    result, model, _, _ = run(product, facts)
    assert model.calls == ["CustomsFacts"]
    assert result.query["candidate_cases"] == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


@pytest.mark.parametrize("bad", [
    select("없는-사례"),
    select(fact_fields=["intended_use"]),           # 확인되지 않은 조건만 근거로 듦
])
def test_대조되지_않는_선택은_버리고_비대상으로_바꾸지_않는다(bad):
    product, facts = product_and_facts()
    result, _, _, requirements = run(product, facts, review(bad))
    assert result.query["dropped_candidates"] == 1 and requirements.calls == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


def test_이유에서_다른_물품이라고_결론_낸_선택은_쓰지_않는다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select(COFFEE_CASE, applies=False), select()))
    assert result.query["not_applicable"] == 1
    assert result.query["selected_cases"] == [KETTLE_CASE]


def test_한_건뿐인_호의_선택은_빼지_않고_HS_확인_필요로_남긴다():
    # 빼면 맞는 후보의 요건·질문도 빠져 효과 평가 전까지 표시만 (#420 리뷰)
    product, facts = product_and_facts()
    result, _, _, requirements = run(product, facts, review(select(), select(COFFEE_CASE)))
    assert result.query["lone_cases"] == [COFFEE_CASE]
    assert result.query["selected_cases"] == [KETTLE_CASE, COFFEE_CASE]
    assert requirements.calls == ["8516799000", "8419810000"]
    assert any("1개(HS 8419.81-0000)가 있어 HS 확인이 필요합니다" in text for text in result.findings[0].assumptions)


def test_원문과_대조되지_않는_조건은_그_조건만_버린다():
    product, facts = product_and_facts()
    facts.facts.append(CustomsFact(field="material", value="유리", evidence_id="listing-0", quote="유리 주전자"))
    result, _, _, _ = run(product, facts, review(select()))
    assert result.query["dropped_facts"] == 1
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED


# 커피 머신(8419.81)에만 수입식품법 요건을 둔 표. 식약 Tool 판단은 통관 요건에 옮기지 않는 법령이라 HS로 갈림
COFFEE_FOOD = Requirement(hs_code="8419810000", law_name="수입식품안전관리 특별법", agency="식품의약품안전처",
                          document="수입식품등의 수입신고확인증", apply_start_date="20200406")


def test_후보_HS의_요건이_다르면_HS를_가르는_조건만_묻고_나머지는_가정으로_남긴다():
    # 전기주전자(8516.79)와 커피 머신(8419.81, 수입식품법 요건) → 재질 답에 따라 알릴 요건이 달라짐
    product, facts = product_and_facts(values=(("product_type", "전기주전자"), ("function", "전기로 물을 끓임")))
    chosen = review(select(needed_fields=["material", "intended_use"]), select(COFFEE_CASE))
    table = {"8516799000": [FakeRequirements.ELECTRICAL], "8419810000": [COFFEE_FOOD]}
    result, _, _, _ = run(product, facts, chosen, requirements=FakeRequirements(table))
    assert result.missing_information == ["제품의 주된 재질(소재) 확인이 필요합니다."]
    assert any("용도 확인이 더 필요합니다" in text for text in result.findings[0].assumptions)


def test_결정사례마다_요청한_같은_조건은_가정에_한_번만_남긴다():
    product, facts = product_and_facts()
    chosen = review(select(needed_fields=["composition"]), select(JUG_CASE, needed_fields=["composition", "intended_use"]))
    result, _, _, _ = run(product, facts, chosen)
    assumptions = result.findings[0].assumptions
    assert [text for text in assumptions if text.startswith("HS 확정에는")] == ["HS 확정에는 구성품, 용도 확인이 더 필요합니다."]


def test_다른_Tool_판단을_따르는_법령만_갈리면_묻지_않는다():
    # 전기주전자(전기용품법)와 커피 머신(요건 없음): 전기용품법은 종합 단계가 electrical 판단으로 맞춤 → HS로 물을 필요 없음
    # (배포 사례: 장난감 9503.00-3700 요건 없음 / 3300 어린이제품법에 "기능" 질문)
    product, facts = product_and_facts(values=(("product_type", "전기주전자"), ("function", "전기로 물을 끓임")))
    chosen = review(select(needed_fields=["material"]), select(COFFEE_CASE))
    result, _, _, _ = run(product, facts, chosen)
    assert result.query["requirements"] == {"8516799000": ["전기용품 및 생활용품 안전관리법"], "8419810000": []}
    assert result.missing_information == []
    assert any("갈리는 세관장확인 요건이 없어 묻지 않았습니다" in text for text in result.findings[0].assumptions)


def test_후보_HS의_요건이_같으면_재질_기능을_묻지_않고_가정으로_남긴다():
    # 후보 HS가 하나뿐이거나 모두 같은 요건이면 답을 들어도 알릴 요건이 같음 (#754: 티셔츠에 기능 질문)
    product, facts = product_and_facts(values=(("product_type", "전기주전자"),))
    chosen = review(select(needed_fields=["material", "function"]), select(JUG_CASE, needed_fields=["function"]))
    result, _, _, _ = run(product, facts, chosen)
    assert result.missing_information == []
    assumptions = result.findings[0].assumptions
    assert "HS 확정에는 재질, 기능 확인이 더 필요하지만, 후보 HS에 따라 갈리는 세관장확인 요건이 없어 묻지 않았습니다." in assumptions
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED


def test_요건이_없는_후보만_남아도_같은_요건으로_보고_묻지_않는다():
    product, facts = product_and_facts(values=(("product_type", "전기주전자"),))
    result, _, _, _ = run(product, facts, review(select(needed_fields=["function"])), requirements=FakeRequirements({}))
    assert result.missing_information == []
    assert result.findings[0].determination is Determination.NOT_REQUIRED


def test_요건을_조회하지_못한_후보가_있으면_재질_기능을_묻는다():
    product, facts = product_and_facts(values=(("product_type", "전기주전자"),))
    unavailable = FakeRequirements(error=EvidenceUnavailable("세관장확인 요건 조회 경로를 쓸 수 없습니다."))
    result, _, _, _ = run(product, facts, review(select(needed_fields=["function"])), requirements=unavailable)
    assert result.missing_information == ["제품에 어떤 기능이 있는지 확인이 필요합니다."]


def test_일부_검색어가_실패해도_나머지로_진행하고_기록한다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()), clip_errors={"전기포트": httpx.ReadTimeout("느림")})
    assert result.query["failed_terms"] == ["전기포트"]
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED


# -- 오류 --

def test_결정사례_조회가_모두_실패하면_Tool_오류다():
    product, facts = product_and_facts(search_terms=("전기주전자",))
    errors = {"전기주전자": httpx.ConnectError("연결 실패")}
    with pytest.raises(CustomsToolError) as caught:
        run(product, facts, review(select()), clip_errors=errors)
    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_GW_조회_오류는_정보부족으로_바꾸지_않는다():
    product, facts = product_and_facts()
    with pytest.raises(CustomsToolError):
        run(product, facts, review(select()), requirements=FakeRequirements(error=httpx.ConnectError("x")))


def test_모델_실패는_공통_Tool_예외로_알린다():
    product, facts = product_and_facts()
    model = Model(facts)
    model.error = TimeoutError("의도한 모델 실패")
    tool = CustomsTool(model, case_search=ClipCaseSearch(lambda: FakeClip([], {})),
                       requirements=FakeRequirements(), evidence=lambda: _EVIDENCE)
    with pytest.raises(CustomsToolError, match="모델 호출") as caught:
        tool.execute(product, decision())
    assert isinstance(caught.value.__cause__, TimeoutError)


def test_미선택은_모델과_조회를_호출하지_않는다():
    product, facts = product_and_facts()
    model = Model(facts)
    result = bare_tool(model).execute(product, decision(selected=False))
    assert result.status is ToolStatus.SKIPPED and model.calls == []


def test_다른_Tool의_선택정보는_실행하지_않는다():
    with pytest.raises(ValueError, match="이름"):
        bare_tool().execute(Product(product_id="p1"),
                            ToolSelectionItem(tool_name=ToolName.RADIO, selected=True, reason="전파"))


# -- Verification 소비 계약 (파이프라인 연결 전) --

def _verify(product: Product, result) -> list:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.CUSTOMS]
    draft = DraftAssessment(product=product, selected_tools=[ToolName.CUSTOMS],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    assert verification.additional_tools_required == []
    return verification.issues


@pytest.mark.parametrize("case", ["candidate", "none", "unavailable", "missing"])
def test_결과는_Verification_규칙_검사를_통과한다(case):
    product, facts = product_and_facts()
    requirements = {"none": FakeRequirements({}),
                    "unavailable": FakeRequirements(error=EvidenceUnavailable("키 없음"))}.get(case)
    if case == "missing":
        facts.facts = [fact for fact in facts.facts if fact.field != "product_type"]
    result, _, _, _ = run(product, facts, review(select()), requirements=requirements)
    assert _verify(product, result) == []


def test_HS_후보_요건_법령은_다른_규제_Tool과_대응한다():
    from app.tools.customs.rules import related_tool
    assert related_tool("전기용품 및 생활용품 안전 관리법") is ToolName.ELECTRICAL
    assert related_tool("어린이제품 안전 특별법") is ToolName.CHILDREN
    assert related_tool("의료기기법") is ToolName.FOOD_DRUG
    assert related_tool("계량에 관한 법률") is None


def test_식품용_기구_요건은_실리콘_주걱_HS에서_찾는다():
    product, facts = product_and_facts("실리콘 주걱, 손잡이 원목, 조리용",
                                       (("product_type", "실리콘 주걱"), ("material", "실리콘")),
                                       search_terms=("실리콘 주걱",))
    result, _, _, _ = run(product, facts, review(select(SPATULA_CASE, fact_fields=["product_type", "material"])))
    assert result.findings[0].subject == "세관 확인 서류가 필요할 수 있음 — 수입식품안전관리 특별법"
    assert result.query["related_tools"] == {"수입식품안전관리 특별법": ToolName.FOOD_DRUG.value}
    assert isinstance(FakeRequirements.FOOD, Requirement)


def test_여러_낱말_검색어는_중심_명사를_바로_뒤에_두어_개수_제한에_잘리지_않게_한다():
    from app.tools.customs.tool import _queries
    assert _queries(["자동 우산", "umbrella", "우산", "3단  자동 접이식 우산", "양수 냄비", "냄비"]) == [
        "자동 우산", "우산", "umbrella", "3단 자동 접이식 우산", "양수 냄비", "냄비"]
    # 리뷰 재현: 여러 낱말 검색어 4개 + 제품 종류 → 예전에는 중심 명사가 모두 잘렸다.
    queries = _queries(["전기 주전자", "electric kettle", "스테인리스 주전자", "무선 주전자", "전기주전자"])
    assert queries[:3] == ["전기 주전자", "주전자", "electric kettle"] and "kettle" in queries


def test_법령명을_별표2와_대응하지_못하면_구매대행_생략_여부를_확인_필요로_둔다():
    product, facts = product_and_facts()
    odd = Requirement(hs_code="8516799000", law_name="전기생활용품안전법(약칭)", agency="국가기술표준원",
                      document="요건확인서")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [odd]}))
    buying = next(text for text in result.required_actions if "구매대행" in text)
    assert buying.split("\n")[-1] == "- 구매대행: 생략 여부를 확인하지 못함"


class _FixedCases:
    def __init__(self, *cases):
        self.cases = cases

    def search(self, queries, terms, *, top_k):
        return CaseCandidates(cases=self.cases)


def test_일부_HS만_요건이_없으면_그_HS도_따로_알린다():
    product, facts = product_and_facts()
    cases = _FixedCases(HsCase(KETTLE_CASE, ("8516799000",), "ELECTRIC KETTLE", "", ""),
                        HsCase(COFFEE_CASE, ("8419810000",), "커피 머신", "", ""))
    tool = CustomsTool(Model(facts, review(select(), select(COFFEE_CASE))), case_search=cases,
                       requirements=FakeRequirements({"8516799000": [FakeRequirements.ELECTRICAL]}),
                       evidence=lambda: _EVIDENCE)
    result = tool.execute(product, decision())
    subjects = [finding.subject for finding in result.findings]
    assert "세관 확인 서류가 필요할 수 있음 — 전기용품 및 생활용품 안전관리법" in subjects
    empty = next(finding for finding in result.findings if finding.subject == "세관 확인 서류 필요 없음")
    # 요건이 있는 다른 후보 카드와 어긋나 보이지 않게, 이 번호로 분류될 때의 결과임을 밝힘
    assert empty.summary == "품목번호: HS 8419.81-0000 후보 (이 번호로 분류될 때)"


def test_문서_ID가_없는_사례는_물품명과_HS로_구분한다():
    from app.clients.customs.schemas.response import CLIPCase
    from app.tools.customs.search import HsCase
    first = HsCase.from_clip(CLIPCase(hs_codes=["3924100000"], product_name="주걱", description="", decision_reason=""))
    second = HsCase.from_clip(CLIPCase(hs_codes=["4419909000"], product_name="주걱", description="", decision_reason=""))
    assert first.case_id != second.case_id


def test_모델_참고값에는_원문_없는_속성의_이름과_값도_들어간다():
    from app.schemas.product import Attribute
    product = Product(product_id="p1", listing_text=["주전자"], attributes=[Attribute(name="품목", value="전기포트")])
    hints = bare_tool()._hints(product)
    assert hints["attributes"] == [{"name": "품목", "value": "전기포트"}]
    assert "listing_text" not in hints


def test_모델을_주지_않으면_Tool_프로필로_모델을_만든다(monkeypatch):
    names = []
    monkeypatch.setattr("app.clients.llm.build_tool_model", lambda name: names.append(name) or Model(None))
    bare_tool()._get_steps()
    assert names == [ToolName.CUSTOMS]


def test_후보에_한_번만_나온_호의_선택은_여러_번_나온_호와_함께_골랐을_때_찾는다():
    from app.tools.customs.tool import _lone_headings
    toy = [HsCase(f"t{i}", ("9503003411",), "STUFFED TOY", "", "") for i in range(3)]
    keyring = HsCase("k", ("6307909000",), "STUFFED TOY 키링", "", "")
    chosen = [(keyring, None, []), (toy[0], None, [])]

    assert _lone_headings(chosen, [*toy, keyring]) == ["k"]


def test_여러_번_나온_호끼리_갈리거나_모두_한_번씩이면_찾지_않는다():
    from app.tools.customs.tool import _lone_headings
    babies = [HsCase(f"b{i}", ("6111201000",), "Babies' garments", "", "") for i in range(2)]
    kids = [HsCase(f"k{i}", ("6109101000",), "CHILDREN'S CLOTHES", "", "") for i in range(3)]
    kettle = HsCase("a", ("8516799000",), "KETTLE", "", "")
    coffee = HsCase("c", ("8419810000",), "COFFEE", "", "")

    assert _lone_headings([(babies[0], None, []), (kids[0], None, [])], [*babies, *kids]) == []
    assert _lone_headings([(kettle, None, []), (coffee, None, [])], [kettle, coffee]) == []


# -- 상품 신호로 빼는 요건 (완구 HS에 걸린 총포법 등) --

_GUN = Requirement(hs_code="9503003919", law_name="총포･도검･화약류 등의 안전관리에 관한 법률", agency="경찰청",
                   document="총포화약류등 수입허가증", apply_start_date="20200406")
_CHILD = Requirement(hs_code="9503003300", law_name="어린이제품 안전 특별법", agency="기술표준원",
                     document="어린이제품 요건확인서", apply_start_date="20200406")


def _toy_result(weapon_like):
    product, facts = product_and_facts()
    product = product.model_copy(update={"weapon_like": weapon_like})
    cases = _FixedCases(HsCase("g", ("9503003919",), "WOODEN TOY", "", ""),
                        HsCase("c", ("9503003300",), "BLOCK TOY", "", ""))
    tool = CustomsTool(Model(facts, review(select("g"), select("c"))), case_search=cases,
                       requirements=FakeRequirements({"9503003919": [_GUN], "9503003300": [_CHILD]}),
                       evidence=lambda: _EVIDENCE)
    return tool.execute(product, decision())


def test_무기_형태가_아닌_상품이면_HS에_걸린_총포법_요건은_빼고_이유를_남긴다():
    result = _toy_result(False)

    subjects = [finding.subject for finding in result.findings]
    assert subjects == ["세관 확인 서류가 필요할 수 있음 — 어린이제품 안전 특별법"]
    assert result.query["excluded_requirements"] == {"9503003919": [_GUN.law_name]}
    assert result.query["requirements"]["9503003919"] == []
    assert result.result.applicable_requirements == ["어린이제품 안전 특별법"]
    assert all("총포" not in text for text in result.required_actions)
    note = next(text for text in result.findings[0].assumptions if "제외했습니다" in text)
    assert "9503.00-3919" in note and "무기 형태 물품" in note


def test_요건을_뺀_HS는_조회_결과_요건_없음으로_안내하지_않는다():
    result = _toy_result(False)

    assert all("세관 확인 서류 필요 없음" not in finding.subject for finding in result.findings)


@pytest.mark.parametrize("weapon_like", [True, None])
def test_무기_형태이거나_모르면_총포법_요건을_남긴다(weapon_like):
    result = _toy_result(weapon_like)

    subjects = [finding.subject for finding in result.findings]
    assert "세관 확인 서류가 필요할 수 있음 — 총포･도검･화약류 등의 안전관리에 관한 법률" in subjects
    assert "excluded_requirements" not in result.query


def test_소가죽_상품의_야생생물법_요건은_빼고_이유를_가정에_남긴다():
    # #640 소가죽 지갑: HS 4202.31에 야생생물법이 걸려 오지만 CITES 종 가죽에만 해당하는 요건
    # 결정사례 가짜는 주전자 검색어만 알아 상품은 주전자 그대로 두고 소재만 소가죽으로 적음 (사실은 원문 인용이 맞아야 남음)
    product, facts = product_and_facts(
        text="소가죽 손잡이 전기주전자, 전기로 물을 끓임. 소재: 탑 레이어 소가죽",
        values=(("product_type", "전기주전자"), ("material", "탑 레이어 소가죽"), ("function", "전기로 물을 끓임")))
    cites = Requirement(hs_code="8516799000", law_name="야생생물 보호 및 관리에 관한 법률(허가)",
                        agency="유역(지방)환경청", document="국제적멸종위기 동식물 수입허가서")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [cites]}))
    assert result.query["excluded_requirements"] == {"8516799000": [cites.law_name]}
    assert result.required_actions == []
    # 요건을 전부 뺀 HS만 남으면 '정보 부족'이 아니라 조회해서 해당 없음으로 본 확정 판단을 남긴다 (카드가 정보 부족으로 나가지 않게)
    [finding] = result.findings
    # 판매자에게는 '요건 없음'과 같은 결론이라 같은 제목과 품목번호로 내고, 뺀 요건은 한 줄로 알림
    assert finding.subject == "세관 확인 서류 필요 없음"
    assert finding.determination is Determination.NOT_REQUIRED and finding.risk_level is RiskLevel.LOW
    assert finding.summary == ("품목번호: HS 8516.79-9000 후보\n"
                               "멸종위기종(CITES) 가죽이나 부위를 쓴 제품에만 필요한 서류는 제외했습니다.")
    assert any("국내 판매 규제" in text for text in finding.assumptions)
    assert finding.legal_sources and finding.legal_sources[0].article == "제226조"
    assert any("멸종위기종(CITES) 가죽이나 부위를 쓴 제품에만 걸리는 요건" in text for text in finding.assumptions)


_CITES = Requirement(hs_code="8516799000", law_name="야생생물 보호 및 관리에 관한 법률(허가)",
                     agency="유역(지방)환경청", document="국제적멸종위기 동식물 수입허가서")


def test_소재로_빠질_요건이_남았는데_재질을_모르면_모델이_요청하지_않아도_재질을_묻는다():
    # #756 리뷰: 가죽 종류를 모르는데 야생생물법이 남아도 모델이 묻지 않음 → 소가죽이면 빠지는 요건이라 코드가 물음
    product, facts = product_and_facts(text="가죽 손잡이 전기주전자, 전기로 물을 끓임",
                                       values=(("product_type", "전기주전자"), ("function", "전기로 물을 끓임")))
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert result.missing_information == ["제품의 주된 재질(소재) 확인이 필요합니다."]
    assert any("소재(가죽 종류 등)에 따라 해당하지 않을 수 있어 재질을 물었습니다" in text
               for text in result.findings[0].assumptions)


def test_재질이_종류를_밝히지_않은_가죽이면_재질을_묻는다():
    product, facts = product_and_facts(text="가죽 손잡이 전기주전자, 전기로 물을 끓임. 소재: 가죽",
                                       values=(("product_type", "전기주전자"), ("material", "가죽")))
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert result.missing_information == ["제품의 주된 재질(소재) 확인이 필요합니다."]


def test_소가죽이나_악어가죽으로_정해지면_재질을_묻지_않는다():
    for leather in ("소가죽", "악어가죽"):
        product, facts = product_and_facts(text=f"{leather} 손잡이 전기주전자, 전기로 물을 끓임. 소재: {leather}",
                                           values=(("product_type", "전기주전자"), ("material", leather)))
        result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
        assert result.missing_information == [], leather


def _answered(product, answer):
    """재질 질문에 판매자가 답한 재진단 입력 (답변 줄을 상품 문구 끝에 붙임, diagnosis/answers.py)."""
    line = f"{ANSWER_PREFIX} 제품의 주된 재질(소재) 확인이 필요합니다. → {answer}"
    return product.model_copy(update={"listing_text": [*product.listing_text, line]})


@pytest.mark.parametrize("answer,left", [("소가죽", False), ("양가죽", False), ("천연가죽", True), ("가죽", True)])
def test_재질_질문에_가죽_종류로_답하면_상품_이름의_가죽이_있어도_요건을_뺀다(answer, left):
    # 리뷰 #774: 상품 이름 "가죽 손잡이 전기주전자"의 "가죽"이 남아 "소가죽"으로 답해도 요건이 빠지지 않았음
    product, facts = product_and_facts(text="가죽 손잡이 전기주전자, 전기로 물을 끓임",
                                       values=(("product_type", "전기주전자"),))
    product = _answered(product.model_copy(update={"product_name": "가죽 손잡이 전기주전자"}), answer)
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert bool(result.query["requirements"]["8516799000"]) is left, answer


def test_재질_질문에_가죽_종류_없이_답하면_다시_묻지_않고_요건을_남긴_이유를_적는다():
    product, facts = product_and_facts(text="가죽 손잡이 전기주전자, 전기로 물을 끓임",
                                       values=(("product_type", "전기주전자"),))
    product = _answered(product.model_copy(update={"product_name": "가죽 손잡이 전기주전자"}), "천연가죽")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert result.missing_information == []
    assumptions = result.findings[0].assumptions
    assert any("판매자 답에서 가죽 종류를 확인하지 못해 남겼습니다" in text for text in assumptions)
    assert not any("재질을 물었습니다" in text for text in assumptions)


def test_이름에_악어가_있으면_소가죽으로_답해도_야생생물법_요건을_남긴다():
    # 남겨야 하는 소재는 답변 줄이 아니라 전체 글로 확인 (안전한 쪽)
    product, facts = product_and_facts(text="악어 무늬 가죽 손잡이 전기주전자, 전기로 물을 끓임",
                                       values=(("product_type", "전기주전자"),))
    product = _answered(product.model_copy(update={"product_name": "악어 무늬 가죽 손잡이 전기주전자"}), "소가죽")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert result.query["requirements"]["8516799000"] == [_CITES.law_name]


def test_상품_정보로_요건을_모두_빼면_세관장확인_필요_칸이_false다():
    product, facts = product_and_facts(
        text="소가죽 손잡이 전기주전자, 전기로 물을 끓임. 소재: 탑 레이어 소가죽",
        values=(("product_type", "전기주전자"), ("material", "탑 레이어 소가죽"), ("function", "전기로 물을 끓임")))
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [_CITES]}))
    assert result.result.applicable_requirements == []
    assert result.result.customs_confirmation_required is False


def test_악어가죽_상품의_야생생물법_요건은_남긴다():
    product, facts = product_and_facts(
        text="악어가죽 손잡이 전기주전자, 전기로 물을 끓임. 소재: 악어가죽",
        values=(("product_type", "전기주전자"), ("material", "악어가죽"), ("function", "전기로 물을 끓임")))
    cites = Requirement(hs_code="8516799000", law_name="야생생물 보호 및 관리에 관한 법률(허가)",
                        agency="유역(지방)환경청", document="국제적멸종위기 동식물 수입허가서")
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({"8516799000": [cites]}))
    assert "excluded_requirements" not in result.query
    assert any("야생생물" in finding.subject for finding in result.findings)
