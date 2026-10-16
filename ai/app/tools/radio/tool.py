"""방송통신기자재 적합성평가 대상 후보 Tool (#297).

흐름: ① 조건 추출(모델, 원문 인용) → ② 대상기자재 조회(코드) → ③ 규칙(코드: 무선 기능 근거, 주파수 정규화)
→ ④ 기자재 선택(모델) → ⑤ 결과 조립(코드: 행 원문·평가유형·판매 방식별 할 일).
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
"""

from typing import Any

from ...prompts import PromptName
from ...schemas.agent import ToolSelectionItem
from ...schemas.product import Product
from ...schemas.radio import RadioFacts, RadioReview
from ...schemas.schemas import (
    Determination, LegalSource, RadioAssessment, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from ..base import RegulatoryTool
from ..common.agent import ToolModelError, ToolStep
from ..common.facts import group_facts, product_snippets, quote_matches
from ..common.law import EvidenceUnavailable, compact
from .evidence import RadioItem
from .rules import ASSESSMENT_PARAGRAPH, band_label, normalized_bands, sale_actions
from .search import RadioCandidates, RadioItemSearch, default_item_search

_FIELDS = {
    "product_type": "제품 종류", "wireless_feature": "무선 기능", "frequency": "사용 주파수",
    "output_power": "출력", "intended_use": "제품 용도",
}
_QUESTIONS = {
    "wireless_feature": "무선 기능(블루투스·Wi-Fi·무선충전·RF 리모컨 등) 정보가 필요합니다.",
}
_REQUIRED_FIELDS = ("product_type", "wireless_feature")
_ASKED_FIELDS = ("frequency",)
_SEARCH_TERMS_LIMIT = 3
_SELECTIONS_LIMIT = 3
_NOTE_LIMIT = 1500


class RadioToolError(ToolModelError):
    """모델·외부 자료 실패. 원본 오류는 예외 체인에만 보존한다."""


class _FactsStep(ToolStep[RadioFacts]):
    component_name = "radio-facts"
    prompt_name = PromptName.RADIO_FACTS
    output_schema = RadioFacts
    error_class = RadioToolError
    failure_label = "전파 Tool 조건 추출"


class _ReviewStep(ToolStep[RadioReview]):
    component_name = "radio-review"
    prompt_name = PromptName.RADIO_REVIEW
    output_schema = RadioReview
    error_class = RadioToolError
    failure_label = "전파 Tool 기자재 선택"


class RadioTool(RegulatoryTool):
    """방송통신기자재 적합성평가(적합인증·적합등록·자기적합확인) 대상 후보를 찾는다. 무선 기능이 있는 상품만 본다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 설정으로 만든다.
        item_search: 대상기자재 조회 경로. None이면 법제처 API 경로(프로세스 공용 캐시)를 쓴다.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 기자재 선택 모델에 넘길 후보 행 수.
    """

    tool_name = ToolName.RADIO

    def __init__(self, model=None, *, item_search: RadioItemSearch | None = None,
                 configured_model: str | None = None, top_k: int = 8):
        if top_k < 1:
            raise ValueError("top_k는 양의 정수여야 합니다.")
        self._model = model
        self._search = item_search
        self._configured_model = configured_model
        self._top_k = top_k
        self._steps: tuple[_FactsStep, _ReviewStep] | None = None

    def _get_steps(self) -> tuple[_FactsStep, _ReviewStep]:
        if self._steps is None:
            if self._model is None:
                # 모델 프로필(#311)의 Tool 표(TOOL_PROFILES)에서 이 Tool의 모델을 고른다.
                from ...config import build_tool_model
                self._model = build_tool_model(self.tool_name)
            options = {"configured_model": self._configured_model}
            self._steps = (_FactsStep(self._model, **options), _ReviewStep(self._model, **options))
        return self._steps

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """미선택은 조회 없이 생략한다. 모델·자료 조회 실패는 예외로 전파해 Executor가 기록한다."""
        if decision.tool_name is not self.tool_name:
            raise ValueError("전파 Tool과 선택된 Tool 이름이 다릅니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, selected=False, selection_reason=decision.reason,
                              status=ToolStatus.SKIPPED)
        query: dict[str, Any] = {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0, "conflicted": []}
        snippets = product_snippets(product)
        if not snippets:
            return self._assemble(decision, [], [], [*_REQUIRED_FIELDS, *_ASKED_FIELDS],
                                  ["입력에 인용 가능한 상품 설명이 없습니다."], query)

        search = self._search or default_item_search()
        try:
            catalog = search.catalog()
        except EvidenceUnavailable:
            catalog = []
        except Exception as exc:
            raise RadioToolError("전파 대상기자재 조회에 실패했습니다.") from exc

        facts_step, review_step = self._get_steps()
        extracted = facts_step.run({"hints": _hints(product), "evidence": snippets, "categories": catalog},
                                   subject_id=product.product_id)
        facts = [fact for fact in extracted.facts if quote_matches(fact, snippets)]
        query["dropped_facts"] = len(extracted.facts) - len(facts)
        by_field = group_facts(facts)
        terms = [term for term in extracted.search_terms if term.strip()][:_SEARCH_TERMS_LIMIT]
        query["search_terms"] = terms
        bands = normalized_bands([fact.value for fact in by_field.get("frequency", [])])
        query["frequency_bands"] = [band_label(band) for band in bands]

        assumptions = ["전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다."]
        if query["dropped_facts"]:
            assumptions.append(f"원문과 대조되지 않은 상품 조건 {query['dropped_facts']}개를 제외했습니다.")
        missing = [field for field in (*_REQUIRED_FIELDS, *_ASKED_FIELDS) if field not in by_field]
        conflicted = [field for field, values in by_field.items()
                      if field in ("product_type",) and len({compact(fact.value) for fact in values}) > 1]
        query["conflicted"] = conflicted
        missing.extend(conflicted)
        if product.conflicts or conflicted:
            assumptions.append("상품 정보에 모순이 있어 적용 조건을 확정하지 않았습니다.")

        if "wireless_feature" not in by_field:
            missing = [field for field in _REQUIRED_FIELDS if field not in by_field]
            assumptions.append("상품 원문에서 무선 기능 근거를 찾지 못해 무선기기 후보를 내지 않았습니다. "
                               "비대상 판단이 아닙니다(유선 전자파적합성 기기는 이 Tool 범위 밖).")
            return self._assemble(decision, facts, [], missing, assumptions, query)
        if any(field not in by_field for field in _REQUIRED_FIELDS) or product.conflicts or conflicted:
            return self._assemble(decision, facts, [], missing, assumptions, query)

        try:
            candidates = search.search(self._terms(terms, by_field, product), top_k=self._top_k)
        except EvidenceUnavailable:
            assumptions.append("법령 대상기자재의 시행 버전·본문을 확인하지 못해 기자재를 대조하지 않았습니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)
        except Exception as exc:
            raise RadioToolError("전파 대상기자재 조회에 실패했습니다.") from exc
        query["documents"] = candidates.documents
        query["candidate_items"] = [item.item_id for item in candidates.items]
        if not candidates.items:
            assumptions.append("상품과 비슷한 대상기자재 행을 찾지 못했습니다. 비대상 판단이 아닙니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)

        sections = list(dict.fromkeys(item.section for item in candidates.items))
        review = review_step.run({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
            "product_bands_mhz": [list(band) for band in bands],
            "section_notes": {section: candidates.section_notes[section][:_NOTE_LIMIT]
                              for section in sections if section in candidates.section_notes},
            "candidates": [item.as_candidate() for item in candidates.items],
        }, subject_id=product.product_id)

        items = {item.item_id: item for item in candidates.items}
        findings, actions, selected = [], [], []
        for selection in review.selections[:_SELECTIONS_LIMIT]:
            if not selection.applies:
                query["not_applicable"] += 1
                continue
            item = items.get(selection.item_id)
            used = [field for field in dict.fromkeys(selection.fact_fields) if field in by_field]
            if item is None or item.item_id in selected or not used:
                query["dropped_candidates"] += 1
                continue
            selected.append(item.item_id)
            missing.extend(field for field in selection.needed_fields if field not in by_field)
            findings.append(self._candidate(item, selection.rationale, used, by_field, candidates, assumptions))
            actions.extend(sale_actions(item, candidates.personal_use))
        query["selected_items"] = selected
        if query["dropped_candidates"]:
            assumptions.append(f"후보 행과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        if not findings:
            assumptions.append("후보 행 중 상품에 맞는 기자재를 고르지 못했습니다. 비대상 판단이 아닙니다.")
        return self._assemble(decision, facts, findings, missing, assumptions, query, actions)

    @staticmethod
    def _terms(terms: list[str], by_field: dict, product: Product) -> list[str]:
        values = [fact.value for field in ("wireless_feature", "product_type", "intended_use")
                  for fact in by_field.get(field, [])]
        hints = [value for value in (product.product_name, product.category) if value]
        return [*terms, *values, *hints]

    def _candidate(self, item: RadioItem, rationale: str, used: list[str], by_field: dict,
                   candidates: RadioCandidates, assumptions: list[str]) -> RegulatoryFinding:
        kind = "·".join(item.assessment) or "적합성평가"
        sources = [candidates.notice.source("별표 1", item.row_text)]
        for assessment in item.assessment:
            paragraph = ASSESSMENT_PARAGRAPH[assessment]
            sources.append(candidates.law.source(f"제58조의2 {paragraph}", candidates.obligation[paragraph]))
        if candidates.personal_use is not None:
            sources.append(candidates.decree.source(f"별표 6의2 {candidates.personal_use.label}목",
                                                    candidates.personal_use.text))
        return RegulatoryFinding(
            tool_name=self.tool_name, subject=f"{kind} 대상기자재 후보 — {item.name}",
            determination=Determination.POSSIBLY_REQUIRED, risk_level=RiskLevel.MEDIUM,
            summary=(f"방송통신기자재 {kind} 대상일 가능성이 있습니다({item.section} > {' > '.join(item.path)}). "
                     "판매 목적 수입은 판매 전 적합성평가가 필요하고, 개인 사용 1대 반입은 면제 대상일 수 있습니다."),
            rationale=rationale, legal_sources=sources,
            product_facts_used=[f"{_FIELDS[field]}: {fact.value} (근거: {fact.quote})"
                                for field in used for fact in by_field[field]],
            assumptions=[*assumptions, "모델 기자재 선택이며 적합성평가 대상·인증 보유를 확정하지 않았습니다. "
                         "평가유형은 고시 별표 1의 행 표시를 그대로 옮겼습니다."],
        )

    def _assemble(self, decision: ToolSelectionItem, facts: list, findings: list[RegulatoryFinding],
                  missing: list[str], assumptions: list[str], query: dict[str, Any],
                  actions: list[str] | None = None) -> ToolResult:
        missing = list(dict.fromkeys(missing))
        if not findings:
            findings = [RegulatoryFinding(
                tool_name=self.tool_name, subject="방송통신기자재 적합성평가 대상 판정",
                determination=Determination.INSUFFICIENT_INFORMATION, risk_level=RiskLevel.UNKNOWN,
                summary="규제 적용을 판단하기 위한 정보·기자재 대응이 부족합니다.",
                rationale="무선 기능 근거 부족·모순 또는 대상기자재와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
                product_facts_used=[f"{_FIELDS[fact.field]}: {fact.value} (근거: {fact.quote})" for fact in facts],
                assumptions=list(assumptions),
            )]
        types = list(dict.fromkeys(
            finding.subject.split(" 대상기자재", 1)[0] for finding in findings
            if finding.determination is Determination.POSSIBLY_REQUIRED))
        detail = RadioAssessment(
            wireless_features=list(dict.fromkeys(fact.value for fact in facts if fact.field == "wireless_feature")),
            frequency_bands=list(query.get("frequency_bands", [])),
            conformity_assessment_required=None,
            certification_type=", ".join(types) or None,
            legal_sources=[],
        )
        conflicted = set(query.get("conflicted", ()))
        return ToolResult(
            tool_name=self.tool_name, selected=True, selection_reason=decision.reason,
            status=ToolStatus.SUCCESS, result=detail, findings=findings,
            required_actions=list(dict.fromkeys(actions or [])),
            missing_information=[f"{_FIELDS[field]} 정보가 서로 달라 확인이 필요합니다." if field in conflicted
                                 else _QUESTIONS.get(field, f"{_FIELDS[field]} 정보가 필요합니다.")
                                 for field in missing],
            query=query,
        )


def _hints(product: Product) -> dict[str, Any]:
    return product.model_dump(mode="json", exclude={"listing_text", "attributes", "source_url"},
                              exclude_none=True)
