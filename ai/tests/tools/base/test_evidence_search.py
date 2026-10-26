"""EvidenceSearchTool: 앞(조건 추출)·뒤(결과 조립) 공통 흐름과 공통 부품. 가짜 하위 Tool로 확인."""

import pytest
from pydantic import BaseModel

from app.prompts import PromptName
from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Attribute, Product
from app.schemas.schemas import Determination, RadioAssessment, RiskLevel, ToolName, ToolStatus
from app.tools.base import EvidenceSearchTool, ToolModelError, ToolStep, ToolStepInput
from app.tools.base.evidence_search import NO_SNIPPETS, SCOPE_NOTE
from app.tools.common.law import EvidenceUnavailable

TEXT = "무선 선풍기, 블루투스 연결"


class _Fact(BaseModel):
    field: str
    value: str
    evidence_id: str
    quote: str


class _Facts(BaseModel):
    facts: list[_Fact]


class _Selection(BaseModel):
    item_id: str
    rationale: str
    applies: bool
    fact_fields: list[str]


class _Review(BaseModel):
    selections: list[_Selection]


class _Error(ToolModelError):
    pass


class _FactsStep(ToolStep[_Facts]):
    component_name = "fake-facts"
    prompt_name = PromptName.RADIO_FACTS
    output_schema = _Facts
    error_class = _Error


class _ReviewStep(ToolStep[_Review]):
    component_name = "fake-review"
    prompt_name = PromptName.RADIO_REVIEW
    output_schema = _Review
    error_class = _Error


class _Structured:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def invoke(self, messages):
        self.owner.calls.append(self.name)
        self.owner.payloads[self.name] = messages[-1].content
        parsed = self.owner.facts if self.name == "_Facts" else self.owner.review
        return {"raw": None, "parsed": parsed, "parsing_error": None}


class _Model:
    model_name = "test-model"

    def __init__(self, facts: _Facts, review: _Review | None = None):
        self.facts = facts
        self.review = review or _Review(selections=[])
        self.calls: list[str] = []
        self.payloads: dict[str, str] = {}

    def with_structured_output(self, schema, **kwargs):
        return _Structured(self, schema["name"])


class _Tool(EvidenceSearchTool):
    tool_name = ToolName.RADIO
    facts_step = _FactsStep
    review_step = _ReviewStep
    error_class = _Error
    field_labels = {"product_type": "제품 종류", "feature": "기능", "power": "전원"}
    questions = {"feature": "기능을 알려 주세요."}
    empty_fields = ("product_type", "feature")
    base_assumptions = ("가짜 Tool 기본 가정.",)
    conflict_note = ". 결과가 달라질 수 있습니다."
    insufficient = ("가짜 판정", "정보가 부족합니다.", "대응이 미확인입니다.")
    tracks_conflicts = True

    def __init__(self, model=None, *, candidates=None, **options):
        super().__init__(model, **options)
        self.candidates = candidates or {}

    def _read_facts(self, run):
        run.assumptions.append("조건을 읽었습니다.")
        run.missing.extend(field for field in ("product_type", "feature") if field not in run.by_field)

    def _judge(self, run):
        _, review_step = self._get_steps()
        review = review_step.run(ToolStepInput({"candidates": list(self.candidates)}, run.product.product_id))
        chosen = self._pick(run, review.selections, self.candidates)
        run.actions.extend(["판매 전 확인", "판매 전 확인"])
        return [self._finding(subject=item, summary="후보", rationale=selection.rationale,
                              determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                              facts=[fact for fact in run.facts if fact.field in used], assumptions=run.assumptions,
                              sources=[]) for item, selection, used in chosen]

    def _detail(self, run, findings):
        return RadioAssessment(wireless_features=[fact.value for fact in run.by_field.get("feature", [])])


def _fact(field, value, quote=TEXT):
    return _Fact(field=field, value=value, evidence_id="listing-0", quote=quote)


def _selection(item_id, applies=True, fields=("product_type",)):
    return _Selection(item_id=item_id, rationale=f"{item_id} 근거", applies=applies, fact_fields=list(fields))


def _decision():
    return ToolSelectionItem(tool_name=ToolName.RADIO, selected=True, reason="무선 기능")


def _product(**fields):
    return Product(product_id="p-1", listing_text=[TEXT], **fields)


FACTS = _Facts(facts=[_fact("product_type", "무선 선풍기"), _fact("feature", "블루투스")])


def test_인용할_원문이_없으면_모델_없이_정보_부족_판단을_돌려준다():
    model = _Model(FACTS)

    result = _Tool(model).execute(Product(product_id="p-1"), _decision())

    assert model.calls == []
    assert result.status is ToolStatus.SUCCESS
    [finding] = result.findings
    assert (finding.subject, finding.determination) == ("가짜 판정", Determination.INSUFFICIENT_INFORMATION)
    assert finding.assumptions == [NO_SNIPPETS]
    assert result.missing_information == ["제품 종류 정보가 필요합니다.", "기능을 알려 주세요."]
    assert result.query == {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0, "conflicted": []}


def test_가정은_원문_범위_기본_버린_조건_Tool_읽기_추출_모순_순서로_남긴다():
    facts = _Facts(facts=[*FACTS.facts, _fact("power", "220V", quote="원문에 없는 인용")])
    model = _Model(facts)

    result = _Tool(model).execute(_product(conflicts=["색상 불일치"]), _decision())

    [finding] = result.findings
    assert finding.assumptions == [
        SCOPE_NOTE, "가짜 Tool 기본 가정.", "원문과 대조되지 않은 상품 조건 1개를 제외했습니다.", "조건을 읽었습니다.",
        "추출 단계가 상품 정보의 모순을 표시했습니다: 색상 불일치. 결과가 달라질 수 있습니다.",
    ]
    assert result.query["dropped_facts"] == 1
    assert finding.product_facts_used == ["제품 종류: 무선 선풍기 (근거: 무선 선풍기, 블루투스 연결)",
                                          "기능: 블루투스 (근거: 무선 선풍기, 블루투스 연결)"]


def test_조건_추출에는_힌트와_원문_조각을_보낸다():
    model = _Model(FACTS)

    _Tool(model).execute(_product(product_name="선풍기", attributes=[Attribute(name="색상", value="흰색")]), _decision())

    assert '"hints": {"product_name": "선풍기"' in model.payloads["_Facts"]
    assert '"evidence": {"listing-0": "무선 선풍기, 블루투스 연결"}' in model.payloads["_Facts"]
    assert '"attributes"' not in model.payloads["_Facts"]


def test_hints_with_attributes면_속성_이름과_값을_힌트에_넣는다():
    class _WithAttributes(_Tool):
        hints_with_attributes = True

    model = _Model(FACTS)

    _WithAttributes(model).execute(_product(attributes=[Attribute(name="색상", value="흰색")]), _decision())

    assert '"attributes": [{"name": "색상", "value": "흰색"}]' in model.payloads["_Facts"]


def test_선택은_해당_없음_후보_밖_중복_근거_없음을_거르고_상한을_적용한다():
    candidates = {f"item-{i}": f"품목 {i}" for i in range(5)}
    review = _Review(selections=[
        _selection("item-0", applies=False), _selection("unknown"), _selection("item-1"), _selection("item-1"),
        _selection("item-2", fields=("power",)), _selection("item-2"), _selection("item-3"), _selection("item-4"),
    ])

    result = _Tool(_Model(FACTS, review), candidates=candidates).execute(_product(), _decision())

    assert [finding.subject for finding in result.findings] == ["품목 1", "품목 2", "품목 3"]
    assert {key: result.query[key] for key in ("not_applicable", "dropped_candidates", "over_limit")} == {
        "not_applicable": 1, "dropped_candidates": 3, "over_limit": 1}
    assert result.findings[0].product_facts_used == ["제품 종류: 무선 선풍기 (근거: 무선 선풍기, 블루투스 연결)"]


def test_pick은_코드_규칙으로_버릴_후보를_받고_상한을_끌_수_있다():
    tool = _Tool()
    run = tool.run_class(_product(), _decision(), by_field={"product_type": [FACTS.facts[0]]})
    selections = [_selection(f"item-{i}") for i in range(5)]

    chosen = tool._pick(run, selections, {f"item-{i}": i for i in range(5)}, limit=None, skip=lambda item: item == 0)

    assert [item for item, _, _ in chosen] == [1, 2, 3, 4]
    assert run.query["dropped_candidates"] == 1


def test_결과는_할_일과_재질문을_중복_없이_모으고_충돌_필드는_확인_문구로_묻는다():
    class _Conflicted(_Tool):
        def _read_facts(self, run):
            run.conflicted.append("product_type")
            run.missing.extend(["product_type", "feature", "feature"])

    model = _Model(_Facts(facts=[_fact("product_type", "무선 선풍기")]))

    result = _Conflicted(model).execute(_product(), _decision())

    assert result.required_actions == ["판매 전 확인"]
    assert result.missing_information == ["제품 종류 정보가 서로 달라 확인이 필요합니다.", "기능을 알려 주세요."]
    assert result.query["conflicted"] == ["product_type"]
    assert result.result.wireless_features == []


def test_lookup은_근거를_확인할_수_없으면_가정을_남기고_None():
    tool = _Tool()
    run = tool.run_class(_product(), _decision())

    def unavailable():
        raise EvidenceUnavailable("버전 없음")

    assert tool._lookup(run, lambda: [1], failure="실패") == [1]
    assert tool._lookup(run, unavailable, failure="실패", unavailable="근거를 확인하지 못했습니다.") is None
    assert tool._lookup(run, unavailable, failure="실패") is None
    assert run.assumptions == ["근거를 확인하지 못했습니다."]


def test_lookup은_그_밖의_조회_실패를_Tool_예외로_바꾸고_원인은_체인에_둔다():
    tool = _Tool()
    cause = ConnectionError("timeout")

    def failing():
        raise cause

    with pytest.raises(_Error, match="조회에 실패했습니다") as caught:
        tool._lookup(tool.run_class(_product(), _decision()), failing, failure="조회에 실패했습니다.")

    assert caught.value.__cause__ is cause


@pytest.mark.parametrize("top_k", [0, -1, True, 2.5])
def test_top_k가_양의_정수가_아니면_ValueError(top_k):
    with pytest.raises(ValueError, match="top_k"):
        _Tool(top_k=top_k)


def test_모델을_주지_않으면_실행할_때_Tool_프로필로_한_번_만들어_두_단계가_같이_쓴다(monkeypatch):
    names = []
    model = _Model(FACTS)
    monkeypatch.setattr("app.clients.llm.build_tool_model", lambda name: names.append(name) or model)

    tool = _Tool(configured_model="test-model")
    assert names == []
    tool.execute(_product(), _decision())
    tool.execute(_product(), _decision())

    assert names == [ToolName.RADIO]
    assert model.calls == ["_Facts", "_Review", "_Facts", "_Review"]
