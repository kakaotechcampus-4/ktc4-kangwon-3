"""표시·광고 Tool. 판매자 문구에서 실증이 필요한 주장을 찾아 근거 조문과 판매 전 할 일을 붙인다.

역할 나눔
- 모델(AdvertisingReviewer): listing_text에서 의심 문구를 원문 그대로 인용하고 유형을 고른다.
- 코드: 인용이 listing_text에 실제로 있는지 대조, 위험도, 근거 조문, 할 일, 질문.

위반을 확정하지 않는다. 부당 여부는 소비자오인성·공정거래저해성으로 판단하고(지정고시 1),
상품 글만으로는 판매자가 실증자료를 갖고 있는지 알 수 없어서 찾은 주장은 POSSIBLY_REQUIRED까지만 쓴다.
찾은 주장이 없으면 NOT_REQUIRED(실증이 필요한 주장 없음) 하나를 남긴다.
근거 조문은 적용 판 본문에서 읽는다(evidence.py). 읽지 못하면 근거 없는 판단을 내지 않고 Tool 실패로 끝낸다.
"""

from collections.abc import Callable

from ...agents.base import ModelLike
from ...observability.trace import trace_note
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
from ..base import RegulatoryTool
from ..common.questions import NO_LISTING_QUESTION
from .errors import AdvertisingEvidenceError
from .evidence import AdvertisingEvidence
from .rules import RISK_ORDER, claim_action, claim_notice, claim_risk, find_kc_claims, normalize, sources_for
from .schemas import AdvertisingClaim, AdvertisingReview
from .steps import AdvertisingReviewer, AdvertisingReviewInput

_NO_LISTING_QUESTION = NO_LISTING_QUESTION.question


class AdvertisingTool(RegulatoryTool):
    tool_name = ToolName.LABEL_AD

    def __init__(self, model: ModelLike | None = None, *, evidence: Callable[[], AdvertisingEvidence],
                 reviewer: AdvertisingReviewer | None = None) -> None:
        """모델은 실제로 문구를 검토할 때 만든다. listing_text가 없으면 모델을 만들거나 부르지 않는다.

        Args:
            model: 구조화 출력을 지원하는 모델. None이면 표시·광고 Tool 프로필(TOOL_PROFILES)로 만든다.
            evidence: 적용 판 근거 조문을 돌려주는 함수.
            reviewer: 테스트·평가용으로 직접 넣는 검토 에이전트. 주면 model은 쓰지 않는다.
        """
        self._model = model
        self._evidence = evidence
        self._reviewer = reviewer

    def _run(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """판매자 문구를 검토해 ToolResult를 돌려준다. 선택 확인·SKIPPED는 RegulatoryTool.execute가 맡음.

        Args:
            product: 추출 에이전트가 만든 상품 정보. listing_text만 검토 대상이다.
            decision: 이 툴의 선택 결정 (selected=True).

        Returns:
            ToolResult: SUCCESS 결과.

        Raises:
            AdvertisingEvidenceError: 근거 조문을 읽지 못함. 실행기가 FAILED로 기록한다.
            AdvertisingReviewError: 모델 호출 또는 파싱 실패. 실행기가 FAILED로 기록한다.
        """
        lines = [line.strip() for line in product.listing_text if line.strip()]
        if not lines:
            return self._no_listing_result(decision)

        # 근거가 없으면 판단을 낼 수 없어 모델 호출 전에 읽음
        try:
            evidence = self._evidence()
        except Exception as exc:
            raise AdvertisingEvidenceError("표시·광고 근거 조문을 읽지 못했습니다.") from exc

        reviewer = self._reviewer or AdvertisingReviewer(self._model)
        review = reviewer.run(AdvertisingReviewInput(product, lines))
        kept, dropped = self._verify_quotes(review.claims, lines)
        # 모델이 놓쳐도 KC 표기는 빠지지 않게 더한다. 모델 인용과 겹치면 모델 쪽을 남긴다.
        kc_added = [
            claim for claim in find_kc_claims(lines)
            if not any(normalize(claim.quote) in normalize(k.quote) or normalize(k.quote) in normalize(claim.quote)
                       for k in kept)
        ]
        # 모델 인용 원문 대조 결과와 코드가 더한 KC 표기 (모델 출력 전체는 호출 파일에)
        trace_note("claims", {"kept": kept, "dropped_quotes": dropped, "kc_added": kc_added})
        return self._assemble(decision, evidence, lines, kept + kc_added, dropped, review, reviewer.prompt.sha256,
                              kc_added=len(kc_added))

    @staticmethod
    def _verify_quotes(
        claims: list[AdvertisingClaim], lines: list[str]
    ) -> tuple[list[AdvertisingClaim], list[str]]:
        """listing_text에 없는 인용을 버리고, 같은 인용은 한 번만 남긴다.

        Args:
            claims: 모델이 인용한 주장.
            lines: 판매자 문구.

        Returns:
            tuple[list[AdvertisingClaim], list[str]]: (남긴 주장, 버린 인용).
        """
        source = [normalize(line) for line in lines]
        kept: list[AdvertisingClaim] = []
        dropped: list[str] = []
        seen: set[str] = set()
        for claim in claims:
            quote = normalize(claim.quote)
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
        evidence: AdvertisingEvidence,
        lines: list[str],
        claims: list[AdvertisingClaim],
        dropped: list[str],
        review: AdvertisingReview,
        prompt_sha256: str,
        kc_added: int = 0,
    ) -> ToolResult:
        """주장마다 위험도·근거·할 일을 붙여 결과를 만든다. 주장이 없으면 '실증이 필요한 주장 없음'을 남긴다.

        Args:
            decision: 이 툴의 선택 결정.
            evidence: 적용 판 근거 조문.
            lines: 판매자 문구.
            claims: 원문과 대조한 주장 (KC 표기 포함).
            dropped: 원문에 없어 버린 인용.
            review: 모델 응답.
            prompt_sha256: 쓴 프롬프트의 해시.
            kc_added: 코드가 더한 KC 표기 주장 수.

        Returns:
            ToolResult: SUCCESS 결과.
        """
        phrases: list[AdvertisingPhrase] = []
        findings: list[RegulatoryFinding] = []
        actions: list[str] = []
        sources: list[LegalSource] = []
        for claim in claims:
            level = claim_risk(claim)
            claim_sources = sources_for(evidence, claim, level)
            action = claim_action(claim, level)
            summary, rationale = claim_notice(claim, level)
            phrases.append(AdvertisingPhrase(text=claim.quote, risk_type=claim.risk_type.value, risk_level=level,
                                             reason=claim.reason, evidence_required=True))
            # 제목은 원문 인용, 영문이면 번역을 괄호로. 채점·원문 대조는 phrases의 text(원문 그대로)로 한다
            subject = f"{claim.quote}({claim.translation})" if claim.translation else claim.quote
            findings.append(RegulatoryFinding(
                tool_name=self.tool_name, subject=subject, determination=Determination.POSSIBLY_REQUIRED,
                risk_level=level, summary=summary, rationale=rationale,
                product_facts_used=[claim.quote], requirements=[action],
                legal_sources=claim_sources,
                assumptions=["판매자가 이 주장의 실증자료를 갖고 있는지는 확인하지 않았습니다."],
            ))
            actions.append(action)
            sources.extend(source for source in claim_sources if source not in sources)

        if not findings:
            # 판단이 비면 검증 규칙이 Tool 실패로 보고 재실행을 요청한다. 찾은 주장이 없다는 판단을 남긴다.
            findings.append(self._no_claim_finding(evidence))
            sources.append(evidence.article_5)

        overall = max((phrase.risk_level for phrase in phrases), key=RISK_ORDER.index, default=RiskLevel.LOW)
        return ToolResult(
            tool_name=self.tool_name,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason=decision.reason,
            query={"listing_lines": len(lines), "prompt_sha256": prompt_sha256, "dropped_quotes": dropped,
                   "kc_claims_added": kc_added, "documents": evidence.documents()},
            result=AdvertisingAssessment(reviewed_phrases=lines, detected_phrases=phrases, overall_risk=overall,
                                         legal_sources=sources),
            findings=findings,
            required_actions=actions,
            # 실증자료가 있는지는 물어도 판단이 바뀌지 않아 질문으로 내지 않는다. 할 일(required_actions)로만 안내한다(#310).
            raw_response=review.model_dump(mode="json"),
        )

    def _no_claim_finding(self, evidence: AdvertisingEvidence) -> RegulatoryFinding:
        """검토한 문구에서 실증이 필요한 주장을 찾지 못한 판단. 모델이 놓쳤을 수 있어 가정에 남긴다.

        Args:
            evidence: 적용 판 근거 조문.

        Returns:
            RegulatoryFinding: NOT_REQUIRED 판단.
        """
        return RegulatoryFinding(
            tool_name=self.tool_name, subject="판매자 상품 문구",
            determination=Determination.NOT_REQUIRED, risk_level=RiskLevel.LOW,
            summary="판매자 문구에서 문제가 될 만한 광고 표현을 찾지 못했습니다.",
            rationale="효능, 인증, 성능, 원재료, 원산지, 최상급 표현, 보증 약속처럼 근거 자료가 필요한 주장이 있는지 확인했습니다.",
            legal_sources=[evidence.article_5],
            assumptions=["추출 단계가 listing_text로 옮긴 판매자 문구만 검토했습니다. 놓친 주장이 있을 수 있습니다."],
        )

    def _no_listing_result(self, decision: ToolSelectionItem) -> ToolResult:
        """검토할 문구가 없으면 모델을 부르지 않고 정보 부족으로 돌려준다. '문제 없음'으로 보지 않는다.

        Args:
            decision: 이 툴의 선택 결정.

        Returns:
            ToolResult: 정보 부족 판단과 재질문을 담은 SUCCESS 결과.
        """
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
                rationale="상세페이지에서 판매자가 쓴 문구를 찾지 못해 광고 표현을 검토하지 못했습니다.",
            )],
            missing_information=[_NO_LISTING_QUESTION],
        )
