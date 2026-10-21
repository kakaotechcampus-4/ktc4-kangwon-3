"""실제 모델·API 없이 통관 Tool 계약을 확인한다. 법령·결정사례는 실제 응답 픽스처를 쓴다."""

import httpx
import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.schemas.customs import CustomsFact, CustomsFacts, CustomsReview, CustomsSelection
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.common.law import EvidenceUnavailable
from app.tools.customs import CustomsTool, CustomsToolError
from app.tools.customs.evidence import load_customs_evidence
from app.tools.customs.search import ClipCaseSearch, Requirement

from .conftest import AS_OF, FakeClip, FakeLaw, FakeRequirements

KETTLE_CASE = "0072016001137"    # 8516.79-9000 ELECTRIC KETTLE(MEK-J12)
JUG_CASE = "0072018002192"       # 8516.79-9000 Cordless Jug Kettle
COFFEE_CASE = "0072017001538"    # 8419.81-0000 커피 머신(다른 물품)
SPATULA_CASE = "0072017003150"   # 3924.10-0000 실리콘 주걱

_EVIDENCE = load_customs_evidence(FakeLaw(), AS_OF)


@pytest.fixture(autouse=True)
def no_usage_file(monkeypatch):
    monkeypatch.setattr("app.usage.record", lambda *a, **kw: None)


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
    assert finding.subject == "세관장확인 대상 후보 — 전기용품 및 생활용품 안전관리법"
    assert "8516.79-9000" in finding.summary and "확정 아님" in finding.summary
    assert result.result.hs_code_candidates == ["8516.79-9000"]
    assert result.result.applicable_requirements == ["전기용품 및 생활용품 안전관리법"]
    assert result.query["selected_cases"] == [KETTLE_CASE]
    assert result.query["related_tools"] == {"전기용품 및 생활용품 안전관리법": ToolName.ELECTRICAL.value}


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


def test_생략_제외_법령은_구매대행이어도_통관_때_요건_확인이_필요할_수_있다고_안내한다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()))
    buying, importing = sorted(result.required_actions, key=lambda text: "구매대행" not in text)
    assert "사입·수입 판매" in importing and "전기용품 및 생활용품 요건확인서" in importing
    assert "생략 대상에서 빠집니다" in buying and "제7조 제2항 제1호 단서" in buying
    # 재실행에서 이 판단이 빠지면 ToolExecutor가 이 판단의 할 일만 지울 수 있다.
    assert set(result.findings[0].requirements) == set(result.required_actions)


def test_생략_제외가_아닌_법령은_대외무역법_시행령_제19조_사유면_생략할_수_있다고_안내한다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()),
                          requirements=FakeRequirements({"8516799000": [FakeRequirements.RADIO]}))
    buying = next(text for text in result.required_actions if "구매대행" in text)
    assert "생략할 수 있습니다" in buying and "해당 여부는 확인이 필요합니다" in buying
    assert result.query["related_tools"] == {"전파법": ToolName.RADIO.value}


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

def test_조회해서_요건이_없으면_정보부족이_아니라_HS_후보_기준_요건_없음으로_낸다():
    product, facts = product_and_facts()
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements({}))
    finding = result.findings[0]
    assert finding.subject == "세관장확인 대상 법령 — HS 후보 기준 없음"
    assert finding.determination is Determination.NOT_REQUIRED
    assert finding.risk_level is RiskLevel.LOW
    assert "국내 판매 규제가 없다는 뜻은 아닙니다" in finding.summary
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


def test_GW가_요건_종류를_붙인_같은_법령은_판단_하나로_묶는다():
    from dataclasses import replace
    permit = replace(FakeRequirements.ELECTRICAL, law_name="전기용품 및 생활용품 안전관리법(허가)", agency="한국제품안전협회")
    product, facts = product_and_facts()
    table = {"8516799000": [FakeRequirements.ELECTRICAL, permit]}
    result, _, _, _ = run(product, facts, review(select()), requirements=FakeRequirements(table))
    candidates = [finding for finding in result.findings if finding.subject.startswith("세관장확인 대상 후보")]
    assert len(candidates) == 1
    assert candidates[0].subject == "세관장확인 대상 후보 — 전기용품 및 생활용품 안전관리법"


def test_GW_키가_없으면_요건_미확인으로_내고_확인_방법을_안내한다():
    product, facts = product_and_facts()
    missing_key = FakeRequirements(error=EvidenceUnavailable("세관장확인 GW 서비스 키(DATA_GO_KR_KEY)가 없어 요건을 조회하지 못했습니다."))
    result, _, _, _ = run(product, facts, review(select()), requirements=missing_key)
    finding = result.findings[0]
    assert finding.subject == "세관장확인 요건 — 조회하지 못함"
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
    assert result.findings[0].subject == "세관장확인 요건 — 조회하지 못함"
    assert result.result.hs_code_candidates == ["8516.79"]


def test_근거_법령을_확인하지_못해도_요건_후보는_내고_생략_여부는_확인_필요로_둔다():
    product, facts = product_and_facts()

    def unavailable():
        raise EvidenceUnavailable("버전 없음")

    result, _, _, _ = run(product, facts, review(select()), evidence=unavailable)
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert [source.source_name for source in finding.legal_sources] == ["관세청 품목분류 결정사례(CLIP)"]
    assert any("생략 여부는 확인이 필요합니다" in text for text in result.required_actions)


# -- 정보 부족·대조 실패 --

def test_제품_종류가_없으면_조회하지_않는다():
    product, facts = product_and_facts(values=(("material", "스테인리스"),))
    result, model, calls, _ = run(product, facts)
    assert model.calls == ["CustomsFacts"] and calls == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.missing_information == ["제품 종류 정보가 필요합니다."]


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


def test_원문과_대조되지_않는_조건은_그_조건만_버린다():
    product, facts = product_and_facts()
    facts.facts.append(CustomsFact(field="material", value="유리", evidence_id="listing-0", quote="유리 주전자"))
    result, _, _, _ = run(product, facts, review(select()))
    assert result.query["dropped_facts"] == 1
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED


def test_HS를_가르는_조건만_묻고_나머지는_가정으로_남긴다():
    product, facts = product_and_facts(values=(("product_type", "전기주전자"), ("function", "전기로 물을 끓임")))
    result, _, _, _ = run(product, facts, review(select(needed_fields=["material", "intended_use"])))
    assert result.missing_information == ["재질 정보가 필요합니다."]
    assert any("용도 확인이 더 필요합니다" in text for text in result.findings[0].assumptions)


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
    result = CustomsTool(model).execute(product, decision(selected=False))
    assert result.status is ToolStatus.SKIPPED and model.calls == []


def test_다른_Tool의_선택정보는_실행하지_않는다():
    with pytest.raises(ValueError, match="이름"):
        CustomsTool().execute(Product(product_id="p1"),
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
    assert result.findings[0].subject == "세관장확인 대상 후보 — 수입식품안전관리 특별법"
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
    assert "확인이 필요합니다" in buying and "생략할 수 있습니다" not in buying


def test_일부_HS만_요건이_없으면_그_HS도_따로_알린다():
    product, facts = product_and_facts()
    chosen = review(select(), select(COFFEE_CASE))
    result, _, _, _ = run(product, facts, chosen, requirements=FakeRequirements({"8516799000": [FakeRequirements.ELECTRICAL]}))
    subjects = [finding.subject for finding in result.findings]
    assert "세관장확인 대상 후보 — 전기용품 및 생활용품 안전관리법" in subjects
    empty = next(finding for finding in result.findings if finding.subject == "세관장확인 대상 법령 — HS 후보 기준 없음")
    assert "8419.81-0000" in empty.summary and "8516.79" not in empty.summary


def test_문서_ID가_없는_사례는_물품명과_HS로_구분한다():
    from app.schemas.clients.customs_response import CLIPCase
    from app.tools.customs.search import HsCase
    first = HsCase.from_clip(CLIPCase(hs_codes=["3924100000"], product_name="주걱", description="", decision_reason=""))
    second = HsCase.from_clip(CLIPCase(hs_codes=["4419909000"], product_name="주걱", description="", decision_reason=""))
    assert first.case_id != second.case_id


def test_모델_참고값에는_원문_없는_속성의_이름과_값도_들어간다():
    from app.schemas.product import Attribute
    from app.tools.customs.tool import _hints
    product = Product(product_id="p1", listing_text=["주전자"], attributes=[Attribute(name="품목", value="전기포트")])
    assert _hints(product)["attributes"] == [{"name": "품목", "value": "전기포트"}]
    assert "listing_text" not in _hints(product)
