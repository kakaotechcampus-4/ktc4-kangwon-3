"""표시·광고 Tool의 코드 몫(인용 대조, 위험도, 근거, 정보 부족)을 가짜 모델로 확인한다.

문구는 평가셋(tests/eval_truth_advertising)과 겹치지 않게 지어냈다. 평가셋 문구로 테스트하면
프롬프트·규칙을 평가셋에 맞추게 된다.
"""

import json
import re
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.agents.verification import VerificationAgent
from app.prompts import PromptName, get_prompt
from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination, DraftAssessment, LegalSource, OverallStatus, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.advertising import rules as advertising
from app.schemas.advertising import AdvertisingReview
from app.tools.advertising import AdvertisingReviewError, AdvertisingReviewer, AdvertisingTool
from app.tools.advertising.tool import _NO_LISTING_QUESTION

LAW_DIR = Path(__file__).parents[2] / "fixtures" / "advertising_law"
DECISION = ToolSelectionItem(tool_name=ToolName.LABEL_AD, selected=True, reason="효능 표방 문구가 있다.")


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


def _claim(quote: str, risk_type: str = "performance_quality") -> dict:
    return {"quote": quote, "risk_type": risk_type, "reason": "실증이 필요한 주장이다."}


def _product(*lines: str) -> Product:
    return Product(product_id="ad-1", product_name="접이식 캠핑 의자", listing_text=list(lines))


def _run(model: _StubModel, *lines: str):
    return AdvertisingTool(model).execute(_product(*lines), DECISION)


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
    assert advertising.MEDICINAL_EFFECT_SOURCE in by_subject["허리 디스크 치료"].legal_sources
    assert advertising.MEDICINAL_EFFECT_SOURCE not in by_subject["자세 개선"].legal_sources


def test_찾은_문구는_확정이_아니라_실증_필요로_돌려준다():
    model = _StubModel([_claim("국내 판매 1위", "ranking_absolute")])

    result = _run(model, "국내 판매 1위 캠핑 의자")

    phrase = result.result.detected_phrases[0]
    finding = result.findings[0]
    assert result.status is ToolStatus.SUCCESS
    assert phrase.evidence_required is True and phrase.risk_type == "ranking_absolute"
    assert finding.determination is Determination.POSSIBLY_REQUIRED
    assert advertising.SUBSTANTIATION_TARGETS[advertising.AdvertisingRiskType.RANKING_ABSOLUTE] in finding.legal_sources
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
    assert finding.legal_sources == [advertising.LAW_ARTICLE_5]
    assert result.required_actions == [] and result.missing_information == []


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

    result = AdvertisingTool(model).execute(_product("방수 원단"), decision)

    assert model.received == []
    assert result.status is ToolStatus.SKIPPED and result.selected is False


def test_다른_툴의_선택_결정은_받지_않는다():
    decision = DECISION.model_copy(update={"tool_name": ToolName.RADIO})

    with pytest.raises(ValueError):
        AdvertisingTool(_StubModel([])).execute(_product("방수 원단"), decision)


def test_모델_호출_실패는_툴_예외로_감싼다():
    with pytest.raises(AdvertisingReviewError):
        _run(_StubModel(error=TimeoutError("timeout")), "방수 원단")


def test_모델에는_표시광고_프롬프트와_판매자_문구를_보낸다():
    model = _StubModel([])

    AdvertisingTool(reviewer=AdvertisingReviewer(model)).execute(_product("방수 원단", " "), DECISION)

    system, human = model.received[0]
    assert system.content == get_prompt(PromptName.ADVERTISING).text
    assert json.loads(human.content) == {"product_name": "접이식 캠핑 의자", "category": None, "listing_text": ["방수 원단"]}


def _law_text() -> str:
    """픽스처 원문을 하나로 이어 공백을 지운 문자열. 조문 JSON은 항 내용까지 펼친다."""
    parts = []
    for path in sorted(LAW_DIR.iterdir()):
        if path.suffix == ".txt":
            parts.append(path.read_text(encoding="utf-8"))
        elif path.suffix == ".json":
            for article in json.loads(path.read_text(encoding="utf-8")):
                parts.append(article["article_content"] or "")
                parts.extend(paragraph["content"] or "" for paragraph in article["paragraphs"])
    return re.sub(r"\s+", "", "".join(parts))


def _all_sources() -> list[LegalSource]:
    return [advertising.LAW_ARTICLE_3, advertising.LAW_ARTICLE_5, advertising.MEDICINAL_EFFECT_SOURCE,
            *advertising.SUBSTANTIATION_TARGETS.values(), *advertising.TYPE_SOURCES.values()]


@pytest.mark.parametrize("source", _all_sources(), ids=lambda source: f"{source.law_name} {source.article}")
def test_근거_인용은_법제처_원문에_그대로_있다(source: LegalSource):
    assert source.is_mock is False
    assert re.sub(r"\s+", "", source.quoted_text) in _law_text()


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


def test_인증이_아닌_안전_주장은_실증자료_안내를_받는다():
    model = _StubModel([_claim("어린이에게 무해한 소재", "safety_certification")])

    result = _run(model, "어린이에게 무해한 소재")

    assert "실증자료" in result.required_actions[0]
