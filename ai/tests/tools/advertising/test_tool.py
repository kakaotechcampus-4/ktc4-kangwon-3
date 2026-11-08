"""표시·광고 Tool의 코드 몫(인용 대조, 위험도, 근거, 정보 부족)을 가짜 모델로 확인한다.

문구는 평가셋(tests/eval_truth_advertising)과 겹치지 않게 지어냈다. 평가셋 문구로 테스트하면
프롬프트·규칙을 평가셋에 맞추게 된다.
"""

import dataclasses
import json
from datetime import date

import pytest
from langchain_core.messages import AIMessage

from app.agents.verification import VerificationAgent
from app.observability.trace import trace_run
from app.prompts import PromptName, get_prompt
from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, OverallStatus, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.advertising import rules as advertising
from app.tools.advertising.schemas import AdvertisingReview, AdvertisingRiskType
from app.tools.advertising import (
    AdvertisingEvidenceError, AdvertisingReviewError, AdvertisingReviewer, AdvertisingTool,
)
from app.tools.advertising.evidence import load_advertising_evidence
from app.tools.advertising.tool import _NO_LISTING_QUESTION
from app.tools.common.law import EvidenceUnavailable

from .conftest import FakeLaw

DECISION = ToolSelectionItem(tool_name=ToolName.LABEL_AD, selected=True, reason="효능 표방 문구가 있다.")
EVIDENCE = load_advertising_evidence(FakeLaw(), date(2026, 11, 7))


class _StubModel:
    """정해진 구조화 출력을 돌려주고 받은 메시지를 기록하는 모델."""

    model_name = "openai/gpt-4.1-mini"

    def __init__(self, claims: list[dict] | None = None, error: Exception | None = None) -> None:
        self._claims = claims or []
        self._error = error
        self.received: list[list] = []

    def with_structured_output(self, schema, **kwargs):
        return self

    def invoke(self, messages: list) -> dict:
        self.received.append(messages)
        if self._error is not None:
            raise self._error
        raw = AIMessage(
            content=json.dumps({"line_checks": [], "claims": self._claims}, ensure_ascii=False),
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            response_metadata={"model_name": self.model_name},
        )
        return {"raw": raw, "parsed": None, "parsing_error": None}


def _claim(quote: str, risk_type: str = "performance_quality", translation: str | None = None) -> dict:
    # translation은 모델 출력 칸이라 None이어도 항상 넣는다 (trace 비교 테스트가 model_dump와 맞춤)
    return {"quote": quote, "risk_type": risk_type, "reason": "실증이 필요한 주장이다.", "translation": translation}


def _product(*lines: str) -> Product:
    return Product(product_id="ad-1", product_name="접이식 캠핑 의자", listing_text=list(lines))


def _tool(model: _StubModel) -> AdvertisingTool:
    return AdvertisingTool(model, evidence=lambda: EVIDENCE)


def _run(model: _StubModel, *lines: str):
    return _tool(model).execute(_product(*lines), DECISION)


def test_listing_text에_없는_인용은_버리고_query에_남긴다():
    model = _StubModel([_claim("하중 300kg 버팀"), _claim("세계 최초 특허 구조", "ranking_absolute")])

    result = _run(model, "접이식 캠핑 의자, 하중 300kg 버팀")

    assert [phrase.text for phrase in result.result.detected_phrases] == ["하중 300kg 버팀"]
    assert result.query["dropped_quotes"] == ["세계 최초 특허 구조"]
    assert len(result.findings) == 1


def test_공백과_영문_대소문자_차이만_같은_인용으로_보고_글자를_바꾼_인용은_버린다():
    model = _StubModel([_claim("UV  차단율 99%"), _claim("자외선 완벽하게 차단")])

    result = _run(model, "uv 차단율 99% 원단", "자외선 완벽 차단")

    assert [phrase.text for phrase in result.result.detected_phrases] == ["UV  차단율 99%"]
    assert result.query["dropped_quotes"] == ["자외선 완벽하게 차단"]


def test_같은_인용은_한_번만_남긴다():
    model = _StubModel([_claim("통기성 2배"), _claim("통기성 2배")])

    result = _run(model, "통기성 2배 메쉬", "통기성 2배 메쉬 등받이")

    assert len(result.result.detected_phrases) == 1
    assert len(result.required_actions) == 1


def test_의약품_효능처럼_읽히는_인체_주장만_위험도를_높이고_근거를_더한다():
    model = _StubModel([_claim("허리 디스크 치료", "body_effect"), _claim("자세 개선", "body_effect"),
                        _claim("방수 원단", "performance_quality")])

    result = _run(model, "허리 디스크 치료, 자세 개선, 방수 원단")

    levels = {phrase.text: phrase.risk_level for phrase in result.result.detected_phrases}
    assert levels == {"허리 디스크 치료": RiskLevel.HIGH, "자세 개선": RiskLevel.MEDIUM, "방수 원단": RiskLevel.MEDIUM}
    assert result.result.overall_risk is RiskLevel.HIGH
    by_subject = {finding.subject: finding for finding in result.findings}
    assert EVIDENCE.medicinal_effect in by_subject["허리 디스크 치료"].legal_sources
    assert EVIDENCE.medicinal_effect not in by_subject["자세 개선"].legal_sources


def test_찾은_문구는_확정이_아니라_실증_필요로_돌려준다():
    model = _StubModel([_claim("국내 판매 1위", "ranking_absolute")])

    result = _run(model, "국내 판매 1위 캠핑 의자")

    phrase = result.result.detected_phrases[0]
    finding = result.findings[0]
    assert result.status is ToolStatus.SUCCESS
    assert phrase.evidence_required is True and phrase.risk_type == "ranking_absolute"
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert EVIDENCE.substantiation_targets[AdvertisingRiskType.RANKING_ABSOLUTE] in finding.legal_sources
    # 실증자료 유무는 답을 받아도 판단이 바뀌지 않아 질문하지 않고 할 일로만 안내한다(#310).
    assert result.missing_information == []
    assert "실증자료" in result.required_actions[0]


def test_근거_조문은_중복_없이_모은다():
    model = _StubModel([_claim("하중 300kg"), _claim("방수 원단")])

    result = _run(model, "하중 300kg, 방수 원단")

    sources = result.result.legal_sources
    assert len(sources) == len({source.model_dump_json() for source in sources}) == 4


def test_의심_문구가_없으면_실증이_필요한_주장_없음_판단_하나를_남긴다():
    result = _run(_StubModel([]), "  접이식 캠핑 의자  ", "", "색상: 카키")

    assert result.result.reviewed_phrases == ["접이식 캠핑 의자", "색상: 카키"]
    assert result.result.detected_phrases == []
    assert result.result.overall_risk is RiskLevel.LOW
    [finding] = result.findings
    assert (finding.determination, finding.risk_level) == (Determination.NOT_REQUIRED, RiskLevel.LOW)
    assert finding.legal_sources == [EVIDENCE.article_5]
    assert result.required_actions == [] and result.missing_information == []


def test_결과_query에_읽은_문서_판을_남긴다():
    result = _run(_StubModel([]), "색상: 카키")

    assert result.query["documents"] == EVIDENCE.documents()


def test_실행할_때마다_그때의_적용_판_근거를_쓴다():
    revised = dataclasses.replace(
        EVIDENCE, article_5=EVIDENCE.article_5.model_copy(update={"quoted_text": "① 개정된 문구"}))
    versions = iter([EVIDENCE, revised])
    tool = AdvertisingTool(_StubModel([]), evidence=lambda: next(versions))

    first = tool.execute(_product("색상: 카키"), DECISION)
    second = tool.execute(_product("색상: 카키"), DECISION)

    assert first.findings[0].legal_sources == [EVIDENCE.article_5]
    assert second.findings[0].legal_sources[0].quoted_text == "① 개정된 문구"


def test_근거를_읽지_못하면_모델을_부르지_않고_Tool_예외로_끝낸다():
    model = _StubModel(error=AssertionError("모델을 부르면 안 된다"))

    def unavailable():
        raise EvidenceUnavailable("문서를 찾지 못했습니다.")

    with pytest.raises(AdvertisingEvidenceError) as caught:
        AdvertisingTool(model, evidence=unavailable).execute(_product("방수 원단"), DECISION)

    assert model.received == []
    assert isinstance(caught.value.__cause__, EvidenceUnavailable)


def test_검토할_문구가_없으면_근거를_읽지_않는다():
    def unexpected():
        raise AssertionError("근거를 읽으면 안 된다")

    result = AdvertisingTool(_StubModel([]), evidence=unexpected).execute(_product(" "), DECISION)

    assert result.status is ToolStatus.SUCCESS
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION


def _verification_issues(result) -> tuple[list, list]:
    skipped = [ToolResult(tool_name=name, selected=False, status=ToolStatus.SKIPPED, selection_reason="범위 밖")
               for name in ToolName if name is not ToolName.LABEL_AD]
    draft = DraftAssessment(product=_product("방수 원단"), selected_tools=[ToolName.LABEL_AD],
                            tool_results=[result, *skipped], findings=result.findings,
                            overall_status=OverallStatus.INSUFFICIENT_INFORMATION, summary="계약 확인")
    verification = VerificationAgent().verify_rules(draft)
    return verification.issues, verification.additional_tools_required


@pytest.mark.parametrize(("claims", "lines"), [
    ([_claim("방수 원단")], ["방수 원단"]),   # 문구 찾음
    ([], ["색상: 카키"]),                    # 문구 없음
    ([], [" "]),                            # 검토할 문구 없음
], ids=["찾음", "없음", "문구_없음"])
def test_결과는_검증_규칙을_통과하고_재실행을_요청받지_않는다(claims, lines):
    result = _run(_StubModel(claims), *lines)

    assert _verification_issues(result) == ([], [])


def test_모델을_넣지_않으면_표시광고_Tool_프로필로_모델을_만든다(monkeypatch):
    names: list[str] = []
    monkeypatch.setattr("app.agents.base.agent.build_agent_model", lambda name: pytest.fail("에이전트 표를 쓰면 안 됨"))
    monkeypatch.setattr("app.agents.base.agent.build_tool_model", lambda name: names.append(name) or _StubModel([]))

    AdvertisingReviewer()

    assert names == [ToolName.LABEL_AD]


def test_listing_text가_비면_모델을_부르지_않고_정보_부족으로_돌려준다():
    model = _StubModel(error=AssertionError("모델을 부르면 안 된다"))

    result = _run(model, " ", "")

    assert model.received == []
    assert result.status is ToolStatus.SUCCESS
    assert result.result.overall_risk is RiskLevel.UNKNOWN
    assert result.findings[0].determination is Determination.INSUFFICIENT_INFORMATION
    assert result.missing_information == [_NO_LISTING_QUESTION]


def test_미선택이면_모델을_부르지_않고_건너뛴다():
    model = _StubModel(error=AssertionError("모델을 부르면 안 된다"))
    decision = DECISION.model_copy(update={"selected": False, "reason": "의심 문구가 없다."})

    result = _tool(model).execute(_product("방수 원단"), decision)

    assert model.received == []
    assert result.status is ToolStatus.SKIPPED and result.selected is False


def test_다른_툴의_선택_결정은_받지_않는다():
    decision = DECISION.model_copy(update={"tool_name": ToolName.RADIO})

    with pytest.raises(ValueError):
        _tool(_StubModel([])).execute(_product("방수 원단"), decision)


def test_모델_호출_실패는_툴_예외로_감싼다():
    with pytest.raises(AdvertisingReviewError):
        _run(_StubModel(error=TimeoutError("timeout")), "방수 원단")


def test_모델에는_상품_이름을_비우고_판매자_문구만_보낸다():
    # 상품 이름이 제목 줄과 같으면 모델이 제목 줄의 효능 구절을 상품 이름으로 보고 빼서 비움 (#349)
    model = _StubModel([])
    reviewer = AdvertisingReviewer(model)

    AdvertisingTool(reviewer=reviewer, evidence=lambda: EVIDENCE).execute(_product("방수 원단", " "), DECISION)

    system, human = model.received[0]
    # 시스템 프롬프트는 광고 프롬프트 + 가드레일
    assert system.content == reviewer.prompt.text
    assert system.content.startswith(get_prompt(PromptName.ADVERTISING).text.rstrip("\n"))
    assert json.loads(human.content) == {"product_name": None, "category": None, "listing_text": ["방수 원단"]}


def test_모델은_줄별_검토를_주장_목록보다_먼저_쓴다():
    # 줄마다 후보를 먼저 쓰게 하자 평가셋 맞힘이 26에서 53/54로 올랐다(mini, 3회). 순서가 바뀌면 효과가 사라진다.
    properties = list(AdvertisingReview.model_json_schema()["properties"])

    assert properties == ["line_checks", "claims"]


@pytest.mark.parametrize(("line", "quotes"), [
    ("접이식 캠핑 의자 KC인증 완료", ["KC인증"]),
    ("kc 안전확인 받은 제품", ["kc 안전확인"]),
    ("인증: KC 방송통신기자재 적합성평가 R-R-ABC-1234", ["KC 방송통신"]),
    ("KC 인증정보: 확인되지 않음", []),        # AliExpress 사양 칸 이름
    ("KCAL 저칼로리 간식", []),
    ("KC 인증을 받은 제품입니다", ["KC 인증"]),
    ("KC 인증 없음", []),                     # 인증이 없다는 문장
    ("KC 인증을 받지 않은 제품입니다", []),
    ("KC인증 미취득", []),
])
def test_국내_인증_표기만_찾는다(line, quotes):
    assert [claim.quote for claim in advertising.find_kc_claims([line])] == quotes


def test_모델이_놓친_KC_표기도_인증_확인_안내와_함께_돌려준다():
    result = _run(_StubModel([]), "접이식 캠핑 의자 KC인증 완료")

    phrase = result.result.detected_phrases[0]
    assert (phrase.text, phrase.risk_type) == ("KC인증", "safety_certification")
    assert "인증번호와 인증서로 확인" in result.required_actions[0]
    assert result.query["kc_claims_added"] == 1


def test_모델이_이미_인용한_KC_표기는_한_번만_남긴다():
    model = _StubModel([_claim("KC인증 완료", "safety_certification")])

    result = _run(model, "접이식 캠핑 의자 KC인증 완료")

    assert [phrase.text for phrase in result.result.detected_phrases] == ["KC인증 완료"]
    assert result.query["kc_claims_added"] == 0


@pytest.mark.parametrize("quote", ["Certified 3C CCC Certified", "CE Certified", "FDA 승인", "RoHS 인증"])
def test_영문_인증_표기도_인증_확인_안내를_받는다(quote):
    # 'Certified 3C CCC Certified'가 실증자료 안내로 나가던 문제 (11/8 측정)
    result = _run(_StubModel([_claim(quote, "safety_certification")]), quote)

    assert "인증번호와 인증서로 확인" in result.required_actions[0]


def test_보증_약속은_보증_확인_안내를_받는다():
    result = _run(_StubModel([_claim("2년 품질 보증", "warranty")]), "2년 품질 보증")

    [finding] = result.findings
    assert finding.summary == "보증 약속 주장으로 실증이 필요할 수 있습니다."
    assert result.required_actions[0].startswith("'2년 품질 보증' 보증 약속이 있습니다. 보증 주체, 기간, 범위를 밝히고")
    assert EVIDENCE.type_sources[AdvertisingRiskType.WARRANTY] in finding.legal_sources


def test_원산지_정품_주장은_수입_서류_확인_안내를_받는다():
    result = _run(_StubModel([_claim("100% 정품", "origin_maker")]), "100% 정품 Made in Korea")

    assert result.required_actions[0].startswith("'100% 정품' 표기가 있습니다. 원산지나 제조자, 정품 여부가 사실인지")
    assert EVIDENCE.type_sources[AdvertisingRiskType.ORIGIN_MAKER] in result.findings[0].legal_sources


def test_영문_인용은_번역을_괄호로_붙여_보여_주고_조사는_번역을_따른다():
    model = _StubModel([_claim("Sunburn Relief", "body_effect", translation="햇볕 화상 완화"),
                        _claim("1 year warranty", "warranty", translation="1년 보증")])

    result = _run(model, "Sunburn Relief 1 year warranty")

    assert [f.subject for f in result.findings] == ["Sunburn Relief(햇볕 화상 완화)", "1 year warranty(1년 보증)"]
    assert result.required_actions[0].startswith("'Sunburn Relief'(햇볕 화상 완화)를 뒷받침하는")
    assert result.required_actions[1].startswith("'1 year warranty'(1년 보증) 보증 약속이 있습니다.")
    # 채점·원문 대조에 쓰는 문구는 원문 그대로
    assert [p.text for p in result.result.detected_phrases] == ["Sunburn Relief", "1 year warranty"]


def test_한국어_인용은_번역_없이_그대로_보여_준다():
    result = _run(_StubModel([_claim("99.9% 살균")]), "99.9% 살균")

    assert result.findings[0].subject == "99.9% 살균"
    assert result.required_actions[0].startswith("'99.9% 살균'을 뒷받침하는")


def test_유형마다_라벨과_근거_조문이_있다():
    for risk_type in AdvertisingRiskType:
        assert risk_type in advertising.TYPE_LABELS and "·" not in advertising.TYPE_LABELS[risk_type]
        assert risk_type in EVIDENCE.substantiation_targets and risk_type in EVIDENCE.type_sources


def test_인증이_아닌_안전_주장은_실증자료_안내를_받는다():
    model = _StubModel([_claim("어린이에게 무해한 소재", "safety_certification")])

    result = _run(model, "어린이에게 무해한 소재")

    assert "실증자료" in result.required_actions[0]


def test_기록_중이면_원문과_대조해_남긴_주장·버린_인용·코드가_더한_KC_표기를_Tool_단계에_남긴다(tmp_path):
    model = _StubModel([_claim("하중 300kg 버팀"), _claim("세계 최초 특허 구조", "ranking_absolute")])

    with trace_run(tmp_path) as recorder:
        _run(model, "접이식 캠핑 의자, 하중 300kg 버팀 KC인증 완료")

    [step] = recorder.steps
    assert step["claims"]["kept"] == [_claim("하중 300kg 버팀")]
    assert step["claims"]["dropped_quotes"] == ["세계 최초 특허 구조"]
    assert [claim["quote"] for claim in step["claims"]["kc_added"]] == ["KC인증"]
    assert [call["component"] for call in step["calls"]] == ["advertising"]
    assert [finding["subject"] for finding in step["result"]["findings"]] == ["하중 300kg 버팀", "KC인증"]


@pytest.mark.parametrize(("quote", "risk_type", "expected"), [
    # 받침이 있으면 을·은, 없으면 를·는 (실사이트 2026-11-06: "'RFID 차단'를 뒷받침하는 …"으로 나감)
    ("습기 차단", "performance_quality", "'습기 차단'을 뒷받침하는"),
    ("오래가는 배터리", "performance_quality", "'오래가는 배터리'를 뒷받침하는"),
    ("관절염 예방", "body_effect", "'관절염 예방'은 의약품 효능처럼"),
    ("불면증 치료", "body_effect", "'불면증 치료'는 의약품 효능처럼"),
    # 문장부호로 끝나면 그 앞 글자의 받침으로 (리뷰 #643)
    ("습기 차단.", "performance_quality", "'습기 차단.'을 뒷받침하는"),
    ("관절염 예방!", "body_effect", "'관절염 예방!'은 의약품 효능처럼"),
])
def test_할_일_문구의_조사는_인용한_문구의_받침에_따라_정한다(quote, risk_type, expected):
    result = _run(_StubModel([_claim(quote, risk_type)]), quote)

    assert result.required_actions[0].startswith(expected)
