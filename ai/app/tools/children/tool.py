"""어린이제품 안전관리 대상 후보 Tool (#296).

흐름: ① 조건 추출(모델, 원문 인용) → ② 품목 조회(코드) → ③ 규칙(코드: 연령·제외 물품) → ④ 품목 선택(모델)
→ ⑤ 결과 조립(코드: 근거 원문·판매 전 할 일).
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
"""

from typing import Any

from ...prompts import PromptName
from ...schemas.agent import ToolSelectionItem
from ...schemas.children import ChildrenFacts, ChildrenReview
from ...schemas.product import Product
from ...schemas.schemas import (
    ChildrenAssessment, Determination, LegalSource, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from ..base import RegulatoryTool
from ..common.agent import ToolModelError, ToolStep
from ..common.facts import group_facts, product_snippets, quote_matches
from ..common.law import EvidenceUnavailable, compact
from .evidence import SCHEME_ANNEXES, SHORT_SCOPE_LIMIT, ChildrenItem, Definitions
from .rules import EXCLUDED_KINDS, age_text, age_value_bounded, combined_child_state, sale_action
from .search import ChildrenCandidates, ChildrenItemSearch, default_item_search

_FIELDS = {
    "product_type": "제품 종류", "target_age": "사용 대상 연령", "intended_use": "제품 용도",
    "material": "재질", "excluded_kind": "제외 물품 해당 여부",
}
_QUESTIONS = {
    "target_age": "사용 대상 연령(예: '만 3세 이상', '36개월 미만') 정보가 필요합니다.",
}
_REQUIRED_FIELDS = ("product_type",)
_SEARCH_TERMS_LIMIT = 3
_SELECTIONS_LIMIT = 3
_LAW_REF = "제2조"
_DOTS = str.maketrans("", "", "·ㆍ?・")


class ChildrenToolError(ToolModelError):
    """모델·외부 자료 실패. 원본 오류는 예외 체인에만 보존한다."""


class _FactsStep(ToolStep[ChildrenFacts]):
    component_name = "children-facts"
    prompt_name = PromptName.CHILDREN_FACTS
    output_schema = ChildrenFacts
    error_class = ChildrenToolError
    failure_label = "어린이제품 Tool 조건 추출"


class _ReviewStep(ToolStep[ChildrenReview]):
    component_name = "children-review"
    prompt_name = PromptName.CHILDREN_REVIEW
    output_schema = ChildrenReview
    error_class = ChildrenToolError
    failure_label = "어린이제품 Tool 품목 선택"


class ChildrenTool(RegulatoryTool):
    """어린이제품 안전관리(안전인증·안전확인·공급자적합성확인) 대상 후보를 찾는다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 설정으로 만든다.
        item_search: 품목 조회 경로. None이면 법제처 API 경로(프로세스 공용 캐시)를 쓴다.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 품목 선택 모델에 넘길 후보 행 수.
    """

    tool_name = ToolName.CHILDREN

    def __init__(self, model=None, *, item_search: ChildrenItemSearch | None = None,
                 configured_model: str | None = None, top_k: int = 6):
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
                from ...config import build_chat_model
                self._model = build_chat_model()
            options = {"configured_model": self._configured_model}
            self._steps = (_FactsStep(self._model, **options), _ReviewStep(self._model, **options))
        return self._steps

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """미선택은 조회 없이 생략한다. 모델·자료 조회 실패는 예외로 전파해 Executor가 기록한다."""
        if decision.tool_name is not self.tool_name:
            raise ValueError("어린이제품 Tool과 선택된 Tool 이름이 다릅니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, selected=False, selection_reason=decision.reason,
                              status=ToolStatus.SKIPPED)
        query: dict[str, Any] = {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0, "conflicted": []}
        snippets = product_snippets(product)
        if not snippets:
            return self._assemble(decision, [], [], ["product_type", "target_age"],
                                  ["입력에 인용 가능한 상품 설명이 없습니다."], query)

        search = self._search or default_item_search()
        try:
            catalog = search.catalog()
        except EvidenceUnavailable:
            catalog = []
        except Exception as exc:
            raise ChildrenToolError("어린이제품 법령 품목표 조회에 실패했습니다.") from exc

        facts_step, review_step = self._get_steps()
        extracted = facts_step.run({"hints": _hints(product), "evidence": snippets, "item_names": catalog,
                                    "excluded_kinds": list(EXCLUDED_KINDS)}, subject_id=product.product_id)
        facts = [fact for fact in extracted.facts
                 if quote_matches(fact, snippets, value_in_quote=fact.field != "excluded_kind")
                 and (fact.field != "excluded_kind" or _excluded_kind(fact.value) is not None)
                 and (fact.field != "target_age" or age_value_bounded(fact.value, fact.quote))]
        query["dropped_facts"] = len(extracted.facts) - len(facts)
        by_field = group_facts(facts)
        terms = [term for term in extracted.search_terms if term.strip()][:_SEARCH_TERMS_LIMIT]
        query["search_terms"] = terms

        assumptions = ["전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다."]
        if query["dropped_facts"]:
            assumptions.append(f"원문과 대조되지 않은 상품 조건 {query['dropped_facts']}개를 제외했습니다.")
        ages = [age_text(fact.value, fact.quote) for fact in by_field.get("target_age", [])]
        if not ages and product.target_age and any(
                compact(product.target_age) in compact(text) for text in snippets.values()):
            ages = [product.target_age]
            query["age_source"] = "product.target_age"
        missing = [field for field in ("product_type",) if field not in by_field]
        if not ages:
            missing.append("target_age")

        query["age_texts"] = ages
        state, age_conflict = combined_child_state(ages)
        if state is False and product.for_children is True:
            state, age_conflict = None, True
            assumptions.append("추출 단계는 만 13세 이하 대상으로 보았으나 표시 연령은 이를 포함하지 않아 "
                               "어린이제품 해당 여부를 정하지 않았습니다.")
        query["age_state"] = state
        if age_conflict:
            query["conflicted"].append("target_age")
            missing.append("target_age")
        if query["conflicted"]:
            assumptions.append("사용 대상 연령 정보가 서로 달라 어린이제품 해당 여부를 정하지 않았습니다.")
        if product.conflicts:
            assumptions.append("추출 단계가 상품 정보의 모순을 표시했습니다: " + "; ".join(product.conflicts)
                               + ". 연령·제품 종류와 관련된 모순이면 결과가 달라질 수 있습니다.")

        try:
            skip_items = (any(field not in by_field for field in _REQUIRED_FIELDS) or state is False
                          or "excluded_kind" in by_field)
            candidates = search.search([] if skip_items else self._terms(terms, by_field, product),
                                       top_k=self._top_k)
        except EvidenceUnavailable:
            assumptions.append("법령 품목표의 시행 버전·본문을 확인하지 못해 품목을 대조하지 않았습니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)
        except Exception as exc:
            raise ChildrenToolError("어린이제품 법령 품목표 조회에 실패했습니다.") from exc
        query["documents"] = candidates.documents
        definitions = candidates.definitions

        excluded = by_field.get("excluded_kind", [])
        if excluded:
            kinds = list(dict.fromkeys(_excluded_kind(fact.value) for fact in excluded))
            query["excluded_kind"] = kinds
            return self._assemble(decision, facts, [self._finding(
                subject="어린이제품 해당 여부 — 제외 물품 가능성",
                summary=(f"어린이제품법 제2조 제1호 단서의 제외 물품({', '.join(kinds)})일 가능성이 있습니다. "
                         "해당하면 어린이제품 안전관리 대상이 아니라 식약 등 다른 법의 검토가 필요합니다. 확정이 아닙니다."),
                rationale="상품 원문에서 제외 물품으로 볼 근거를 찾았습니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=assumptions,
                sources=[definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product)],
            )], [field for field in missing if field != "target_age"], assumptions, query)

        if state is False:
            return self._assemble(decision, facts, [self._finding(
                subject="어린이제품 해당 여부 — 사용 연령",
                summary="표시된 사용 연령이 만 13세 이하를 포함하지 않아 어린이제품이 아닐 가능성이 있습니다. 확정이 아닙니다.",
                rationale="법 제2조 제1호는 만 13세 이하 어린이가 사용하거나 어린이를 위해 사용되는 물품을 어린이제품으로 봅니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=assumptions,
                sources=[definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product)],
            )], missing, assumptions, query)

        if any(field not in by_field for field in _REQUIRED_FIELDS):
            return self._assemble(decision, facts, [], missing, assumptions, query)

        # 조회 상위 품목에 안전인증·안전확인 품목 전체를 더한다. 맞는 품목이 없을 때 공급자적합성확인으로 낮춰 안내하므로,
        # 두 제도의 품목이 조회 순위에서 빠져 모델이 못 본 채로 낮춰지는 일이 없게 한다.
        # 순위 밖 품목은 적용범위를 짧게 넣는다(전문을 모두 넣으면 입력이 약 4배로 늘었다, 실측).
        ranked = set(candidates.items)
        review_items = list(dict.fromkeys([*candidates.items, *candidates.designated]))
        query["candidate_items"] = [item.item_id for item in review_items]
        findings, actions, selected = [], [], []
        if review_items:
            review = review_step.run({
                "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
                "age_state": state,
                "candidates": [item.as_candidate() if item in ranked else item.as_candidate(SHORT_SCOPE_LIMIT)
                               for item in review_items],
            }, subject_id=product.product_id)
            items = {item.item_id: item for item in review_items}
            for selection in review.selections:
                if not selection.applies:
                    query["not_applicable"] += 1
                    continue
                item = items.get(selection.item_id)
                used = [field for field in dict.fromkeys(selection.fact_fields) if field in by_field]
                if item is None or item.item_id in selected or not used:
                    query["dropped_candidates"] += 1
                    continue
                if len(selected) >= _SELECTIONS_LIMIT:
                    query["over_limit"] = query.get("over_limit", 0) + 1
                    continue
                selected.append(item.item_id)
                missing.extend(field for field in selection.needed_fields if field not in by_field)
                action = sale_action(item.scheme, item.name)
                findings.append(self._candidate(item, selection.rationale, used, by_field, definitions, state,
                                                assumptions, candidates, action))
                actions.append(action)
        query["selected_items"] = selected
        if query["dropped_candidates"]:
            assumptions.append(f"후보 행과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")

        if not findings:
            common = candidates.common_standard
            if state is True and not query["dropped_candidates"]:
                query["fallback"] = common.item_id
                action = sale_action(common.scheme, "공통안전기준 적용 품목")
                findings.append(self._finding(
                    subject="공급자적합성확인대상 어린이제품 후보 — 개별 안전기준이 없는 품목",
                    summary=("안전인증·안전확인 품목에 맞는 것을 찾지 못했습니다. 만 13세 이하 대상 어린이제품이면 "
                             "공급자적합성확인대상이고 어린이제품 공통안전기준이 적용될 가능성이 있습니다. 확정이 아닙니다."),
                    rationale="법 제2조 제12호는 안전인증·안전확인대상이 아닌 어린이제품을 공급자적합성확인대상으로 정합니다.",
                    determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                    facts=facts, assumptions=[*assumptions, "품목 선택에서 맞는 행을 찾지 못한 결과입니다."],
                    sources=[definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product),
                             definitions.law.source(f"{_LAW_REF} 제12호", definitions.supplier_product),
                             _rule_source(candidates, common)],
                    requirements=[action],
                ))
                actions.append(action)
            elif query["dropped_candidates"]:
                assumptions.append("품목 선택 결과를 원문·후보와 대조하지 못해 품목을 정하지 않았습니다. "
                                   "안전인증·안전확인 품목일 수 있어 공급자적합성확인으로 낮춰 안내하지 않았습니다.")
            else:
                assumptions.append("후보 품목 중 맞는 것을 고르지 못했습니다. 비대상 판단이 아닙니다. "
                                   "만 13세 이하 대상이면 최소한 공급자적합성확인대상입니다(법 제2조 제12호).")
        if findings:
            assumptions.append("어린이제품법에서 구매대행 특례 조문을 찾지 못해 구매대행·사입을 나누지 않았습니다.")
        return self._assemble(decision, facts, findings, missing, assumptions, query, actions)

    @staticmethod
    def _terms(terms: list[str], by_field: dict, product: Product) -> list[str]:
        values = [fact.value for field in ("product_type", "intended_use") for fact in by_field.get(field, [])]
        hints = [value for value in (product.product_name, product.category, product.intended_use) if value]
        return [*terms, *values, *hints]

    def _candidate(self, item: ChildrenItem, rationale: str, used: list[str], by_field: dict,
                   definitions: Definitions, state: bool | None, assumptions: list[str],
                   candidates: ChildrenCandidates, action: str) -> RegulatoryFinding:
        sources = [_rule_source(candidates, item)]
        if item.scopes:
            sources.append(_notice_source(candidates, item))
        notes = ["모델 품목 선택이며 규제 적용·인증 보유를 확정하지 않았습니다."]
        summary = (f"이 품목으로 분류되면 {item.scheme.value}대상 어린이제품일 가능성이 있습니다(확정 아님). "
                   f"적용 안전기준: {', '.join(item.standards)}.")
        if state is True:
            sources.append(definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product))
        elif state is None:
            summary += " 사용 대상 연령을 확인하지 못했습니다. 만 13세 이하 대상일 때 적용됩니다."
        return RegulatoryFinding(
            tool_name=self.tool_name, subject=f"{item.scheme.value}대상 어린이제품 후보 — {item.name}",
            determination=Determination.POSSIBLY_REQUIRED, risk_level=RiskLevel.MEDIUM,
            summary=summary, rationale=rationale, legal_sources=sources, requirements=[action],
            product_facts_used=[f"{_FIELDS[field]}: {fact.value} (근거: {fact.quote})"
                                for field in used for fact in by_field[field]],
            assumptions=[*assumptions, *notes],
        )

    def _finding(self, *, subject: str, summary: str, rationale: str, determination: Determination,
                 risk: RiskLevel, facts: list, assumptions: list[str], sources: list[LegalSource],
                 requirements: list[str] | None = None) -> RegulatoryFinding:
        return RegulatoryFinding(
            tool_name=self.tool_name, subject=subject, determination=determination, risk_level=risk,
            summary=summary, rationale=rationale, legal_sources=sources, requirements=list(requirements or []),
            product_facts_used=[f"{_FIELDS[fact.field]}: {fact.value} (근거: {fact.quote})" for fact in facts],
            assumptions=list(assumptions),
        )

    def _assemble(self, decision: ToolSelectionItem, facts: list, findings: list[RegulatoryFinding],
                  missing: list[str], assumptions: list[str], query: dict[str, Any],
                  actions: list[str] | None = None) -> ToolResult:
        missing = list(dict.fromkeys(missing))
        if not findings:
            findings = [self._finding(
                subject="어린이제품 안전관리 대상 판정",
                summary="규제 적용을 판단하기 위한 정보·품목 대응이 부족합니다.",
                rationale="조건 부족·모순 또는 품목표와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=assumptions, sources=[],
            )]
        ages = query.get("age_texts") or [fact.value for fact in facts if fact.field == "target_age"]
        types = [fact.value for fact in facts if fact.field == "product_type"]
        schemes = list(dict.fromkeys(
            finding.subject.split("대상", 1)[0] for finding in findings
            if finding.determination is Determination.POSSIBLY_REQUIRED))
        detail = ChildrenAssessment(
            target_age_raw=ages[0] if ages else None,
            intended_for_children=query.get("age_state"),
            product_type=types[0] if types else None,
            safety_management_required=None,
            certification_type=", ".join(schemes) or None,
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


def _excluded_kind(value: str) -> str | None:
    """제외 물품 값을 정해진 이름으로 맞춘다. 공백·가운뎃점(·, ㆍ, ?) 차이는 무시한다."""
    key = compact(value).translate(_DOTS)
    return next((kind for kind in EXCLUDED_KINDS if compact(kind).translate(_DOTS) == key), None)


def _hints(product: Product) -> dict[str, Any]:
    """조건 추출 모델에 주는 참고값. 판단 근거가 아니며 인용은 evidence에서만 한다."""
    return product.model_dump(mode="json", exclude={"listing_text", "attributes", "source_url"},
                              exclude_none=True)


def _rule_source(candidates: ChildrenCandidates, item: ChildrenItem) -> LegalSource:
    return candidates.rule.source(f"별표 {SCHEME_ANNEXES[item.scheme][0]}", item.row_text)


def _notice_source(candidates: ChildrenCandidates, item: ChildrenItem) -> LegalSource:
    return candidates.notice.source(f"별표 {SCHEME_ANNEXES[item.scheme][1]}", " ".join(item.scopes))
