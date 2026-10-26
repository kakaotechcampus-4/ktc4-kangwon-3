"""실제 모델·API 없이 전파 Tool 계약을 확인한다. 대상기자재는 실제 법제처 응답 픽스처를 쓴다."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.radio import RadioFact, RadioFacts, RadioReview, RadioSelection
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, ToolName, ToolResult, ToolStatus,
)
from app.tools.common.law import EvidenceUnavailable
from app.tools.radio import RadioTool, RadioToolError
from app.tools.radio.evidence import load_radio_evidence
from app.tools.radio.search import LawApiItemSearch

from .conftest import AS_OF, FakeLaw

DATA_ROW = "LARN8"
AUDIO_ROW = "LARN4"
_EVIDENCE = load_radio_evidence(FakeLaw(), AS_OF)


class _Structured:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def invoke(self, messages):
        self.owner.calls.append(self.name)
        self.owner.last_payload[self.name] = messages[-1].content
        if self.owner.error is not None:
            raise self.owner.error
        parsed = self.owner.facts if self.name == "RadioFacts" else self.owner.review
        return {"raw": None, "parsed": parsed, "parsing_error": None}


class Model:
    model_name = "test-model"

    def __init__(self, facts, review=None):
        self.facts = facts
        self.review = review or RadioReview(selections=[])
        self.calls: list[str] = []
        self.last_payload: dict[str, str] = {}
        self.error: Exception | None = None

    def with_structured_output(self, schema, **kwargs):
        assert kwargs.get("include_raw") is True
        return _Structured(self, schema["name"])


class Search:
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


def decision(selected=True):
    return ToolSelectionItem(tool_name=ToolName.RADIO, selected=selected, reason="블루투스 기능")


def product_and_facts(text="블루투스 무선 이어폰, Bluetooth 5.3, 2.4GHz",
                      values=(("product_type", "무선 이어폰"), ("wireless_feature", "Bluetooth 5.3"),
                              ("frequency", "2.4GHz")),
                      search_terms=("특정소출력무선기기", "무선데이터통신시스템용무선기기")):
    product = Product(product_id="p1", listing_text=[text])
    facts = RadioFacts(
        facts=[RadioFact(field=field, value=value, evidence_id="listing-0", quote=text) for field, value in values],
        search_terms=list(search_terms),
    )
    return product, facts


def select(item_id=DATA_ROW, **changes):
    values = dict(item_id=item_id, rationale="2.4GHz 블루투스 데이터 전송 기기로 무선데이터통신시스템용에 해당할 가능성이 있습니다.",
                  applies=True, fact_fields=["wireless_feature", "frequency"], needed_fields=[])
    values.update(changes)
    return RadioSelection(**values)


def review(*selections):
    return RadioReview(selections=list(selections))


def run(product, facts, chosen=None, search=None):
    model, search = Model(facts, chosen), search or Search()
    result = RadioTool(model, item_search=search).execute(product, decision())
    return result, model, search


def test_미선택이면_모델과_조회를_부르지_않는다():
    product, facts = product_and_facts()
    model, search = Model(facts), Search()
    result = RadioTool(model, item_search=search).execute(product, decision(False))
    assert result.status is ToolStatus.SKIPPED
    assert model.calls == [] and search.calls == []


def test_맞는_기자재를_고르면_평가유형과_근거와_판매_방식별_할_일을_낸다():
    product, facts = product_and_facts()
    result, model, search = run(product, facts, review(select()))
    assert model.calls == ["RadioFacts", "RadioReview"]
    assert DATA_ROW in result.query["candidate_items"]
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert finding.subject == "적합인증 대상기자재 후보 — 무선데이터통신시스템용무선기기"
    assert [source.article for source in finding.legal_sources] == ["별표 1", "제58조의2 ②", "별표 6의2 자목"]
    assert all(not source.is_mock and source.quoted_text and source.source_url for source in finding.legal_sources)
    assert len(result.required_actions) == 2
    assert result.required_actions[0].startswith("[무선데이터통신시스템용무선기기 · 적합인증 후보] 사입·수입 판매:")
    assert "적합인증을 받은 제품인지" in result.required_actions[0]
    assert "개인 사용 목적으로 1대" in result.required_actions[1] and "확인이 필요합니다" in result.required_actions[1]
    assert result.result.certification_type == "적합인증"
    assert result.result.wireless_features == ["Bluetooth 5.3"]
    assert result.result.frequency_bands == ["2400 MHz"]
    assert result.result.conformity_assessment_required is None


def test_평가유형은_모델이_아니라_행_표시를_따른다():
    product, facts = product_and_facts("블루투스 스피커 무선 음향 전송", (
        ("product_type", "블루투스 스피커"), ("wireless_feature", "무선 음향 전송")),
        ("특정소출력무선기기", "음성 및 음향신호전송용무선기기"))
    result, _, _ = run(product, facts, review(select(AUDIO_ROW, fact_fields=["wireless_feature"])))
    assert result.findings[0].subject.startswith("적합등록 대상기자재 후보")
    assert [source.article for source in result.findings[0].legal_sources][1] == "제58조의2 ③"


def test_무선_기능_원문_근거가_없으면_후보를_내지_않는다():
    product, facts = product_and_facts("유선 USB 키보드", (("product_type", "유선 USB 키보드"),), ("키보드",))
    product.wireless_comm = True
    result, model, search = run(product, facts, review(select()))
    assert model.calls == ["RadioFacts"]
    assert search.calls == []
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert any("무선 기능 근거를 찾지 못해" in note for note in result.findings[0].assumptions)
    assert result.missing_information == ["무선 기능(블루투스·Wi-Fi·무선충전·RF 리모컨 등) 정보가 필요합니다."]


def test_주파수는_판단을_바꾸지_않아_질문하지_않고_가정으로_남긴다():
    product, facts = product_and_facts("블루투스 무선 이어폰", (
        ("product_type", "무선 이어폰"), ("wireless_feature", "블루투스")))
    result, _, _ = run(product, facts, review(select(fact_fields=["wireless_feature"], needed_fields=["frequency"])))
    finding = result.findings[0]
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert result.missing_information == []
    assert any("사용 주파수" in note for note in finding.assumptions)


def test_무선_기능_값_안의_주파수도_읽는다():
    text = "블루투스 무선 이어폰, Bluetooth 5.0 (2.4GHz)"
    product, facts = product_and_facts(text, (
        ("product_type", "무선 이어폰"), ("wireless_feature", "Bluetooth 5.0 (2.4GHz)")))
    result, _, _ = run(product, facts, review(select()))
    assert result.query["frequency_bands"] == ["2400 MHz"]


def test_추출_단계의_상품_모순은_조회를_막지_않고_가정으로만_남긴다():
    product, facts = product_and_facts()
    product = product.model_copy(update={"conflicts": ["배터리 용량이 1200mAh와 1500mAh로 다르게 적혀 있음"]})
    result, _, search = run(product, facts, review(select()))
    assert search.calls, "모순이 있어도 대상기자재를 조회해야 합니다."
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED
    assert any("배터리 용량" in note for note in result.findings[0].assumptions)


def test_제품_종류가_여러_값이어도_충돌이_아니라_모두_조회어로_쓴다():
    text = "블루투스 무선 이어폰 겸 헤드셋, Bluetooth 5.3, 2.4GHz"
    product, facts = product_and_facts(text, (
        ("product_type", "무선 이어폰"), ("product_type", "헤드셋"), ("wireless_feature", "Bluetooth 5.3")))
    result, _, search = run(product, facts, review(select()))
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED
    assert {"무선 이어폰", "헤드셋"} <= set(search.calls[0])
    assert result.missing_information == []


def test_해당_없음이_앞에_여러_개여도_뒤의_맞는_행을_고른다():
    product, facts = product_and_facts()
    not_applicable = [select(item_id=AUDIO_ROW, applies=False) for _ in range(3)]
    result, _, _ = run(product, facts, review(*not_applicable, select()))
    assert result.query["selected_items"] == [DATA_ROW]
    assert result.query["not_applicable"] == 3


def test_판단마다_그_행의_판매_안내를_연결한다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select()))
    finding = result.findings[0]
    assert finding.requirements and set(finding.requirements) <= set(result.required_actions)


def test_기자재_선택_모델에_정규화한_주파수와_절_비고를_준다():
    product, facts = product_and_facts()
    _, model, _ = run(product, facts, review(select()))
    payload = model.last_payload["RadioReview"]
    assert '"product_bands_mhz": [[2400.0, 2400.0]]' in payload
    assert '"section_notes"' in payload and "20cm" in payload
    assert '"assessment": ["적합인증"]' in payload


def test_조건_추출_모델에_대상기자재_분류명_목록을_준다():
    product, facts = product_and_facts()
    _, model, _ = run(product, facts, review(select()))
    assert '"categories"' in model.last_payload["RadioFacts"]
    assert "특정소출력무선기기 > 무선데이터통신시스템용무선기기" in model.last_payload["RadioFacts"]


@pytest.mark.parametrize("bad", [select("NOPE"), select(fact_fields=["output_power"])])
def test_대조되지_않는_선택은_버리고_비대상으로_바꾸지_않는다(bad):
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(bad))
    assert result.query["dropped_candidates"] == 1
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


def test_이유에서_해당하지_않는다고_결론_낸_선택은_후보로_내지_않는다():
    product, facts = product_and_facts()
    result, _, _ = run(product, facts, review(select(), select(AUDIO_ROW, applies=False)))
    assert result.query["selected_items"] == [DATA_ROW]
    assert result.query["not_applicable"] == 1


def test_원문과_대조되지_않는_조건은_그_조건만_버린다():
    product, facts = product_and_facts()
    facts.facts[2].value = "5GHz"
    result, _, _ = run(product, facts, review(select(fact_fields=["wireless_feature"])))
    assert result.query["dropped_facts"] == 1
    assert result.query["frequency_bands"] == []
    assert result.findings[0].determination is Determination.POSSIBLY_REQUIRED


def test_근거_버전을_확인하지_못하면_정보부족으로_끝낸다():
    product, facts = product_and_facts()
    result, model, _ = run(product, facts, review(select()), Search(EvidenceUnavailable("버전 없음")))
    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert model.calls == ["RadioFacts"]


def test_조회_오류는_Tool_오류로_전파한다():
    product, facts = product_and_facts()
    with pytest.raises(RadioToolError):
        run(product, facts, review(select()), Search(RuntimeError("API 실패")))


def test_모델_호출_실패는_Tool_오류로_감싼다():
    product, facts = product_and_facts()
    model = Model(facts)
    model.error = TimeoutError("timeout")
    with pytest.raises(RadioToolError):
        RadioTool(model, item_search=Search()).execute(product, decision())


def _verify(product: Product, result) -> list:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.RADIO]
    draft = DraftAssessment(product=product, selected_tools=[ToolName.RADIO],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    assert verification.additional_tools_required == []
    return verification.issues


@pytest.mark.parametrize("case", ["candidate", "no_wireless", "empty"])
def test_결과는_Verification_규칙_검사를_통과한다(case):
    product, facts = product_and_facts()
    chosen = review(select())
    if case == "no_wireless":
        product, facts = product_and_facts("유선 USB 키보드", (("product_type", "유선 USB 키보드"),), ("키보드",))
    elif case == "empty":
        chosen = review()
    result, _, _ = run(product, facts, chosen)
    assert _verify(product, result) == []


def test_모델을_주지_않으면_Tool_프로필로_모델을_만든다(monkeypatch):
    names = []
    monkeypatch.setattr("app.config.build_tool_model", lambda name: names.append(name) or Model(None))
    RadioTool(item_search=Search())._get_steps()
    assert names == [ToolName.RADIO]
