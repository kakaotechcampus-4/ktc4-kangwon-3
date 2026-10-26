"""표시·광고 Tool. 판매자 문구에서 실증이 필요한 주장을 찾아 근거 조문과 판매 전 할 일을 붙인다.

역할 나눔
- 모델(AdvertisingReviewer): listing_text에서 의심 문구를 원문 그대로 인용하고 유형을 고른다.
- 코드: 인용이 listing_text에 실제로 있는지 대조, 위험도, 근거 조문, 할 일, 질문.

위반을 확정하지 않는다. 부당 여부는 소비자오인성·공정거래저해성으로 판단하고(지정고시 1),
상품 글만으로는 판매자가 실증자료를 갖고 있는지 알 수 없어서 찾은 주장은 POSSIBLY_REQUIRED까지만 쓴다.
찾은 주장이 없으면 NOT_REQUIRED(실증이 필요한 주장 없음) 하나를 남긴다.
근거 조문 원문은 tests/fixtures/advertising_law에 고정했고, 아래 인용 문구가 원문과 같은지 테스트가 확인한다.
"""

import json
import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from ..base import RegulatoryTool
from ...agents.base import AgentError, BaseAgent, ModelFailurePhase, ModelLike
from ...prompts import PromptName
from ...schemas.advertising import AdvertisingClaim, AdvertisingReview, AdvertisingRiskType
from ...schemas.agent import ToolSelectionItem
from ...schemas.product import Product
from ...schemas.schemas import (
    AdvertisingAssessment,
    AdvertisingPhrase,
    Determination,
    LegalSource,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
)

_SOURCE_NAME = "국가법령정보센터"
# 버전(MST·일련번호)을 고정한 공개 열람 주소. 요청 URL(OC 포함)은 쓰지 않는다.
_LAW_URL = "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=268659"
_DESIGNATION_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000184414"
_SUBSTANTIATION_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000284664"
_AWARD_CERT_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000070475"
_CONSUMER_SAFETY_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000056062"

_LAW_NAME = "표시ㆍ광고의 공정화에 관한 법률"
_DESIGNATION = "부당한 표시·광고행위의 유형 및 기준 지정고시"
_SUBSTANTIATION = "표시ㆍ광고 내용의 실증에 관한 운영 고시"
_AWARD_CERT = "수상·인증 등의 표시·광고에 관한 심사지침"
_CONSUMER_SAFETY = "소비자 안전에 관한 표시·광고 심사지침"


def _source(law_name: str, article: str, quoted_text: str, url: str, effective_date: str) -> LegalSource:
    return LegalSource(
        source_name=_SOURCE_NAME, law_name=law_name, article=article, quoted_text=quoted_text,
        source_url=url, effective_date=effective_date, is_mock=False,
    )


# quoted_text는 픽스처 원문에서 그대로 옮겼다(test_advertising_sources가 대조).
LAW_ARTICLE_3 = _source(
    _LAW_NAME, "제3조 제1항",
    "① 사업자등은 소비자를 속이거나 소비자로 하여금 잘못 알게 할 우려가 있는 표시ㆍ광고 행위로서 공정한 거래질서를 "
    "해칠 우려가 있는 다음 각 호의 행위를 하거나 다른 사업자등으로 하여금 하게 하여서는 아니 된다.",
    _LAW_URL, "2025-01-21",
)
LAW_ARTICLE_5 = _source(
    _LAW_NAME, "제5조 제1항",
    "① 사업자등은 자기가 한 표시ㆍ광고 중 사실과 관련한 사항에 대하여는 실증(實證)할 수 있어야 한다.",
    _LAW_URL, "2025-01-21",
)
SUBSTANTIATION_TARGETS = {
    AdvertisingRiskType.BODY_EFFECT: _source(
        _SUBSTANTIATION, "Ⅲ 1", "1. 인체에 직접적으로 영향을 미친다는 내용", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.SAFETY_CERTIFICATION: _source(
        _SUBSTANTIATION, "Ⅲ 2", "2. 안전 또는 환경, 신기술과 관련된 내용인 경우", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.PERFORMANCE_QUALITY: _source(
        _SUBSTANTIATION, "Ⅲ 3", "3. 성능, 효능, 품질에 관한 내용인 경우", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.RANKING_ABSOLUTE: _source(
        _SUBSTANTIATION, "Ⅲ 4", "4. 기타 소비자의 구매선택 및 거래질서에 중대한 영향을 미치는 내용",
        _SUBSTANTIATION_URL, "2026-09-03"),
}
TYPE_SOURCES = {
    AdvertisingRiskType.BODY_EFFECT: _source(
        _DESIGNATION, "5 라",
        "라. 표시ㆍ광고된 상품의 성능이나 효능이 객관적으로 확인될 수 없거나 확인되지 아니하였는데도 불구하고 "
        "확실하게 발휘되는 것처럼 표시ㆍ광고하는 행위",
        _DESIGNATION_URL, "2019-12-12"),
    AdvertisingRiskType.SAFETY_CERTIFICATION: _source(
        _AWARD_CERT, "Ⅴ 1",
        "1. 수상·인증·선정·특허 등의 사실이 없음에도 불구하고 이러한 사실이 있는 것처럼 표시·광고하는 행위는 "
        "부당한 표시·광고에 해당할 수 있다.",
        _AWARD_CERT_URL, "2016-12-23"),
    AdvertisingRiskType.PERFORMANCE_QUALITY: _source(
        _DESIGNATION, "5 라",
        "라. 표시ㆍ광고된 상품의 성능이나 효능이 객관적으로 확인될 수 없거나 확인되지 아니하였는데도 불구하고 "
        "확실하게 발휘되는 것처럼 표시ㆍ광고하는 행위",
        _DESIGNATION_URL, "2019-12-12"),
    AdvertisingRiskType.RANKING_ABSOLUTE: _source(
        _DESIGNATION, "14 나",
        "자기자신이나 자기가 공급하는 상품(이하\"자기의 것\"이라 한다)이 경쟁사업자의 것보다 현저히 우량 또는 유리하다고 "
        "나타내기 위하여 \"최대\", \"최고\", \"최초\", \"제일\", \"유일\"등 배타성을 띤 절대적 표현의 용어를 사용하여 "
        "소비자를 오인시킬 우려가 있는 표시ㆍ광고행위는 부당한 표시ㆍ광고가 된다.",
        _DESIGNATION_URL, "2019-12-12"),
}
MEDICINAL_EFFECT_SOURCE = _source(
    _CONSUMER_SAFETY, "Ⅴ 1 가",
    "의약품이 아닌 상품의 효능 등을 객관적 근거 없이 의약품의 효능이 있는 것처럼 사실과 다르게 소비자를 오인시킬 "
    "우려가 있는 표시·광고행위는 부당한 표시·광고가 된다.",
    _CONSUMER_SAFETY_URL, "2016-08-03",
)

# 의약품 효능처럼 읽히는 낱말. 소비자 안전 지침 Ⅴ 1 가가 "부당한 표시·광고가 된다"로 단정하는 유형이라 위험도를 높인다.
_MEDICINAL_WORDS = ("치료", "예방", "완치", "질병", "질환")

# 국내 인증(KC) 표기. 실제 인증 여부는 상품 글만으로 알 수 없어 모델 판단과 관계없이 코드가 찾아 확인을 안내한다.
# "KC 인증정보"는 AliExpress 사양 칸 이름이라 뺀다(값이 "확인되지 않음"인 경우가 있다).
# "KC 인증 없음"·"KC 인증을 받지 않은"처럼 인증이 없다는 문장은 인증 주장이 아니라 뺀다.
_KC_MARK = re.compile(r"(?<![A-Za-z])KC\s*(?:인증(?!정보)|마크|안전인증|안전확인|공급자적합성|방송통신|적합성평가|certifi\w*)"
                      r"(?!\s*(?:이|을|은)?\s*(?:없|받지\s*않|미))",
                      re.IGNORECASE)
_KC_REASON = "국내 인증(KC) 표기다. 실제로 인증을 받은 제품인지 상품 글만으로는 확인할 수 없다."

_TYPE_LABELS = {
    AdvertisingRiskType.BODY_EFFECT: "인체 효능·효과",
    AdvertisingRiskType.SAFETY_CERTIFICATION: "안전·인증",
    AdvertisingRiskType.PERFORMANCE_QUALITY: "성능·품질",
    AdvertisingRiskType.RANKING_ABSOLUTE: "순위·절대적 표현",
}
_RISK_ORDER = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
_NO_LISTING_QUESTION = "판매자가 쓴 상품 설명·홍보 문구가 없어 표시·광고를 검토하지 못했습니다. 상세페이지의 상품 설명 문구를 알려주세요."


class AdvertisingReviewError(AgentError):
    """표시·광고 문구 검토 모델 호출 또는 파싱 실패."""


@dataclass(frozen=True)
class AdvertisingReviewInput:
    """문구 검토 입력.

    Attributes:
        product: 사용량 기록과 문맥(상품 이름·종류)에 쓸 상품.
        lines: 검토할 판매자 문구. 빈 줄은 뺀 listing_text.
    """

    product: Product
    lines: list[str]


class AdvertisingReviewer(BaseAgent[AdvertisingReviewInput, AdvertisingReview, AdvertisingReview]):
    """listing_text에서 실증이 필요한 주장을 인용하는 모델 호출부."""

    component_name = "advertising"
    # Tool 안에서 쓰는 에이전트라 TOOL_PROFILES의 표시·광고 Tool 프로필로 모델을 고름
    model_profile = ("tool", ToolName.LABEL_AD)
    prompt_name = PromptName.ADVERTISING
    output_schema = AdvertisingReview
    error_class = AdvertisingReviewError

    def _build_messages(self, input: AdvertisingReviewInput) -> list[SystemMessage | HumanMessage]:
        """상품 이름·종류와 판매자 문구로 모델 메시지를 만든다.

        Args:
            input: 문구 검토 입력.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.
        """
        product = input.product
        payload = {"product_name": product.product_name, "category": product.category, "listing_text": input.lines}
        return self._messages(json.dumps(payload, ensure_ascii=False))

    def _subject_id(self, input: AdvertisingReviewInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 문구 검토 입력.

        Returns:
            str: 상품 ID.
        """
        return input.product.product_id

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 문구를 만든다. 원인은 예외 이름만 넣음.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        # 응답을 못 받은 실패
        if phase is ModelFailurePhase.CALL:
            return f"표시·광고 문구 검토 모델 호출에 실패했습니다: {type(cause).__name__}"
        return f"모델 응답이 AdvertisingReview 스키마와 맞지 않습니다: {type(cause).__name__}"


def _normalize(text: str) -> str:
    """대조용 정규화. 공백 차이와 영문 대소문자만 무시한다. 글자를 바꾼 인용은 그대로 다르게 본다."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def find_kc_claims(lines: list[str]) -> list[AdvertisingClaim]:
    """국내 인증(KC) 표기를 찾는다. 같은 표기는 한 번만 돌려준다."""
    found: dict[str, AdvertisingClaim] = {}
    for line in lines:
        for match in _KC_MARK.finditer(line):
            quote = match.group(0)
            found.setdefault(_normalize(quote), AdvertisingClaim(
                quote=quote, risk_type=AdvertisingRiskType.SAFETY_CERTIFICATION, reason=_KC_REASON))
    return list(found.values())


def _is_certification(claim: AdvertisingClaim) -> bool:
    return claim.risk_type is AdvertisingRiskType.SAFETY_CERTIFICATION and (
        "인증" in claim.quote or _KC_MARK.search(claim.quote) is not None)


def _risk_level(claim: AdvertisingClaim) -> RiskLevel:
    if claim.risk_type is AdvertisingRiskType.BODY_EFFECT and any(word in claim.quote for word in _MEDICINAL_WORDS):
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def _sources_for(claim: AdvertisingClaim, risk_level: RiskLevel) -> list[LegalSource]:
    sources = [LAW_ARTICLE_3, LAW_ARTICLE_5, SUBSTANTIATION_TARGETS[claim.risk_type], TYPE_SOURCES[claim.risk_type]]
    if risk_level is RiskLevel.HIGH:
        sources.append(MEDICINAL_EFFECT_SOURCE)
    return sources


def _action(claim: AdvertisingClaim, risk_level: RiskLevel) -> str:
    if _is_certification(claim):
        return (f"'{claim.quote}' 표기가 있습니다. 실제로 인증을 받은 제품인지 인증번호와 인증서로 확인하고, "
                "확인되지 않으면 표기를 빼세요.")
    if risk_level is RiskLevel.HIGH:
        return (f"'{claim.quote}'는 의약품 효능처럼 읽힙니다. 의약품이 아닌 상품이면 문구를 빼거나 고치고, "
                "남기려면 객관적 근거 자료를 먼저 확인하세요.")
    return f"'{claim.quote}'를 뒷받침하는 시험·조사 자료(실증자료)를 준비하거나, 자료가 없으면 문구를 빼거나 고치세요."


class AdvertisingTool(RegulatoryTool):
    tool_name = ToolName.LABEL_AD

    def __init__(self, model: ModelLike | None = None, *, reviewer: AdvertisingReviewer | None = None) -> None:
        """모델은 실제로 문구를 검토할 때 만든다. listing_text가 없으면 모델을 만들거나 부르지 않는다.

        Args:
            model: 구조화 출력을 지원하는 모델. None이면 표시·광고 Tool 프로필(TOOL_PROFILES)로 만든다.
            reviewer: 테스트·평가용으로 직접 넣는 검토 에이전트. 주면 model은 쓰지 않는다.
        """
        self._model = model
        self._reviewer = reviewer

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """판매자 문구를 검토해 ToolResult를 돌려준다.

        Args:
            product: 추출 에이전트가 만든 상품 정보. listing_text만 검토 대상이다.
            decision: 이 툴의 선택 결정.

        Returns:
            ToolResult: 미선택이면 SKIPPED, 그 밖에는 SUCCESS.

        Raises:
            ValueError: 다른 툴의 선택 결정을 받은 경우.
            AdvertisingReviewError: 모델 호출 또는 파싱 실패. 실행기가 FAILED로 기록한다.
        """
        if decision.tool_name is not self.tool_name:
            raise ValueError("표시·광고 Tool에 다른 툴의 선택 결정이 들어왔습니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, status=ToolStatus.SKIPPED, selected=False,
                              selection_reason=decision.reason)

        lines = [line.strip() for line in product.listing_text if line.strip()]
        if not lines:
            return self._no_listing_result(decision)

        reviewer = self._reviewer or AdvertisingReviewer(self._model)
        review = reviewer.run(AdvertisingReviewInput(product, lines))
        kept, dropped = self._verify_quotes(review.claims, lines)
        # 모델이 놓쳐도 KC 표기는 빠지지 않게 더한다. 모델 인용과 겹치면 모델 쪽을 남긴다.
        kc_added = [
            claim for claim in find_kc_claims(lines)
            if not any(_normalize(claim.quote) in _normalize(k.quote) or _normalize(k.quote) in _normalize(claim.quote)
                       for k in kept)
        ]
        return self._assemble(decision, lines, kept + kc_added, dropped, review, reviewer.prompt.sha256,
                              kc_added=len(kc_added))

    @staticmethod
    def _verify_quotes(
        claims: list[AdvertisingClaim], lines: list[str]
    ) -> tuple[list[AdvertisingClaim], list[str]]:
        """listing_text에 없는 인용을 버리고, 같은 인용은 한 번만 남긴다."""
        source = [_normalize(line) for line in lines]
        kept: list[AdvertisingClaim] = []
        dropped: list[str] = []
        seen: set[str] = set()
        for claim in claims:
            quote = _normalize(claim.quote)
            if not quote or not any(quote in line for line in source):
                dropped.append(claim.quote)
                continue
            if quote in seen:
                continue
            seen.add(quote)
            kept.append(claim)
        return kept, dropped

    def _assemble(
        self,
        decision: ToolSelectionItem,
        lines: list[str],
        claims: list[AdvertisingClaim],
        dropped: list[str],
        review: AdvertisingReview,
        prompt_sha256: str,
        kc_added: int = 0,
    ) -> ToolResult:
        phrases: list[AdvertisingPhrase] = []
        findings: list[RegulatoryFinding] = []
        actions: list[str] = []
        sources: list[LegalSource] = []
        for claim in claims:
            level = _risk_level(claim)
            claim_sources = _sources_for(claim, level)
            action = _action(claim, level)
            phrases.append(AdvertisingPhrase(text=claim.quote, risk_type=claim.risk_type.value, risk_level=level,
                                             reason=claim.reason, evidence_required=True))
            findings.append(RegulatoryFinding(
                tool_name=self.tool_name, subject=claim.quote, determination=Determination.POSSIBLY_REQUIRED,
                risk_level=level, summary=f"{_TYPE_LABELS[claim.risk_type]} 주장으로 실증이 필요할 수 있습니다.",
                rationale=claim.reason, product_facts_used=[claim.quote], requirements=[action],
                legal_sources=claim_sources,
                assumptions=["판매자가 이 주장의 실증자료를 갖고 있는지는 확인하지 않았습니다."],
            ))
            actions.append(action)
            sources.extend(source for source in claim_sources if source not in sources)

        if not findings:
            # 판단이 비면 검증 규칙이 Tool 실패로 보고 재실행을 요청한다. 찾은 주장이 없다는 판단을 남긴다.
            findings.append(self._no_claim_finding())
            sources.append(LAW_ARTICLE_5)

        overall = max((phrase.risk_level for phrase in phrases), key=_RISK_ORDER.index, default=RiskLevel.LOW)
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason=decision.reason,
            query={"listing_lines": len(lines), "prompt_sha256": prompt_sha256, "dropped_quotes": dropped,
                   "kc_claims_added": kc_added},
            result=AdvertisingAssessment(reviewed_phrases=lines, detected_phrases=phrases, overall_risk=overall,
                                         legal_sources=sources),
            findings=findings,
            required_actions=actions,
            # 실증자료가 있는지는 물어도 판단이 바뀌지 않아 질문으로 내지 않는다. 할 일(required_actions)로만 안내한다(#310).
            raw_response=review.model_dump(mode="json"),
        )

    def _no_claim_finding(self) -> RegulatoryFinding:
        """검토한 문구에서 실증이 필요한 주장을 찾지 못한 판단. 모델이 놓쳤을 수 있어 가정에 남긴다."""
        return RegulatoryFinding(
            tool_name=self.tool_name, subject="판매자 상품 문구",
            determination=Determination.NOT_REQUIRED, risk_level=RiskLevel.LOW,
            summary="검토한 판매자 문구에서 실증이 필요한 주장을 찾지 못했습니다.",
            rationale="실증 운영 고시 Ⅲ 1~4(인체·안전·성능·순위)에 해당하는 사실 주장을 찾지 못했습니다.",
            legal_sources=[LAW_ARTICLE_5],
            assumptions=["추출 단계가 listing_text로 옮긴 판매자 문구만 검토했습니다. 놓친 주장이 있을 수 있습니다."],
        )

    def _no_listing_result(self, decision: ToolSelectionItem) -> ToolResult:
        """검토할 문구가 없으면 모델을 부르지 않고 정보 부족으로 돌려준다. '문제 없음'으로 보지 않는다."""
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason=decision.reason,
            query={"listing_lines": 0},
            result=AdvertisingAssessment(overall_risk=RiskLevel.UNKNOWN),
            findings=[RegulatoryFinding(
                tool_name=self.tool_name, subject="판매자 상품 문구",
                determination=Determination.INSUFFICIENT_INFORMATION, risk_level=RiskLevel.UNKNOWN,
                summary="검토할 판매자 문구가 없습니다.",
                rationale="listing_text가 비어 있어 표시·광고 문구를 검토하지 않았습니다.",
            )],
            missing_information=[_NO_LISTING_QUESTION],
        )
