"""어린이제품 안전관리 대상 후보 Tool (#296).

흐름: ① 조건 추출(모델, 원문 인용) → ② 품목 조회(코드) → ③ 규칙(코드: 연령·제외 물품) → ④ 품목 선택(모델)
→ ⑤ 결과 조립(코드: 근거 원문·판매 전 할 일).
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
"""

from dataclasses import dataclass, field
from typing import Any

from ...schemas.product import Product
from ...schemas.schemas import ChildrenAssessment, Determination, LegalSource, RegulatoryFinding, RiskLevel, ToolName
from ..base import EvidenceSearchTool, ToolRun, ToolStepInput
from ..common.facts import quote_matches
from ..common.law import compact
from .errors import ChildrenToolError
from .evidence import SCHEME_ANNEXES, SHORT_SCOPE_LIMIT, ChildrenItem
from .rules import EXCLUDED_KINDS, age_text, age_value_bounded, combined_child_state, sale_action
from .search import ChildrenCandidates, ChildrenItemSearch
from .steps import ChildrenFactsStep, ChildrenReviewStep

_FIELDS = {
    "product_type": "제품 종류", "target_age": "사용 대상 연령", "intended_use": "제품 용도",
    "material": "재질", "excluded_kind": "제외 물품 해당 여부",
}
_QUESTIONS = {
    "target_age": "사용 대상 연령(예: '만 3세 이상', '36개월 미만') 정보가 필요합니다.",
}
_REQUIRED_FIELDS = ("product_type",)
_SEARCH_TERMS_LIMIT = 3
_SEARCH_FAILED = "어린이제품 법령 품목표 조회에 실패했습니다."
_LAW_REF = "제2조"
_DOTS = str.maketrans("", "", "·ㆍ?・")


@dataclass
class ChildrenRun(ToolRun):
    """어린이제품 Tool 실행 상태. 품목 목록·조회어·연령 판정을 더 가짐.

    Attributes:
        catalog: 조건 추출 모델에 줄 품목 이름 목록.
        terms: 모델이 낸 조회어 (최대 3개).
        state: 만 13세 이하 대상 여부. None이면 정하지 않음.
    """

    catalog: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    state: bool | None = None


class ChildrenTool(EvidenceSearchTool):
    """어린이제품 안전관리(안전인증·안전확인·공급자적합성확인) 대상 후보를 찾는다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 설정으로 만든다.
        item_search: 품목 조회 경로.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 품목 선택 모델에 넘길 후보 행 수.
    """

    tool_name = ToolName.CHILDREN
    facts_step = ChildrenFactsStep
    review_step = ChildrenReviewStep
    error_class = ChildrenToolError
    field_labels = _FIELDS
    questions = _QUESTIONS
    empty_fields = ("product_type", "target_age")
    conflict_note = ". 연령·제품 종류와 관련된 모순이면 결과가 달라질 수 있습니다."
    insufficient = (
        "어린이제품 안전관리 대상 판정",
        "규제 적용을 판단하기 위한 정보·품목 대응이 부족합니다.",
        "조건 부족·모순 또는 품목표와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
    )
    tracks_conflicts = True
    run_type = ChildrenRun

    def __init__(self, model=None, *, item_search: ChildrenItemSearch, configured_model: str | None = None,
                 top_k: int = 6):
        super().__init__(model, configured_model=configured_model, top_k=top_k)
        self._search = item_search

    def _prepare(self, run: ChildrenRun) -> None:
        """품목 이름 목록을 읽는다. 근거를 확인할 수 없으면 목록 없이 추출.

        Args:
            run: 이번 실행 상태.
        """
        run.catalog = self._lookup(run, self._search.catalog, failure=_SEARCH_FAILED) or []

    def _facts_payload(self, run: ChildrenRun) -> dict[str, Any]:
        """조건 추출 입력에 품목명 목록과 제외 물품 이름을 더한다.

        Args:
            run: 이번 실행 상태.

        Returns:
            dict[str, Any]: 조건 추출 단계 입력.
        """
        return {**super()._facts_payload(run), "item_names": run.catalog, "excluded_kinds": list(EXCLUDED_KINDS)}

    def _fact_matches(self, fact, run: ChildrenRun) -> bool:
        """원문 대조에 더해 제외 물품은 정해진 이름, 연령은 원문 범위 안의 값인지 확인한다.

        Args:
            fact: 모델이 뽑은 조건.
            run: 이번 실행 상태.

        Returns:
            bool: 원문과 맞으면 True.
        """
        return (quote_matches(fact, run.snippets, value_in_quote=fact.field != "excluded_kind")
                and (fact.field != "excluded_kind" or _excluded_kind(fact.value) is not None)
                and (fact.field != "target_age" or age_value_bounded(fact.value, fact.quote)))

    def _read_facts(self, run: ChildrenRun) -> None:
        """조회어와 사용 연령을 읽고 만 13세 이하 대상 여부와 연령 충돌을 기록한다.

        Args:
            run: 이번 실행 상태.
        """
        product, by_field, query = run.product, run.by_field, run.query
        run.terms = [term for term in run.extracted.search_terms if term.strip()][:_SEARCH_TERMS_LIMIT]
        query["search_terms"] = run.terms
        ages = [age_text(fact.value, fact.quote) for fact in by_field.get("target_age", [])]
        if not ages and product.target_age and any(
                compact(product.target_age) in compact(text) for text in run.snippets.values()):
            ages = [product.target_age]
            query["age_source"] = "product.target_age"
        run.missing = [name for name in ("product_type",) if name not in by_field]
        if not ages:
            run.missing.append("target_age")

        query["age_texts"] = ages
        state, age_conflict = combined_child_state(ages)
        if state is False and product.for_children is True:
            state, age_conflict = None, True
            run.assumptions.append("추출 단계는 만 13세 이하 대상으로 보았으나 표시 연령은 이를 포함하지 않아 "
                                   "어린이제품 해당 여부를 정하지 않았습니다.")
        run.state = query["age_state"] = state
        if age_conflict:
            run.conflicted.append("target_age")
            run.missing.append("target_age")
        if run.conflicted:
            run.assumptions.append("사용 대상 연령 정보가 서로 달라 어린이제품 해당 여부를 정하지 않았습니다.")

    def _judge(self, run: ChildrenRun) -> list[RegulatoryFinding]:
        """품목 조회 → 제외 물품·연령 규칙 → 품목 선택 → 후보 판단 (맞는 품목이 없으면 공급자적합성확인).

        Args:
            run: 이번 실행 상태.

        Returns:
            list[RegulatoryFinding]: 고른 품목별 후보 판단. 근거가 부족하면 빈 목록.
        """
        product, by_field, query, state = run.product, run.by_field, run.query, run.state
        skip_items = (any(name not in by_field for name in _REQUIRED_FIELDS) or state is False
                      or "excluded_kind" in by_field)
        candidates = self._lookup(
            run, lambda: self._search.search([] if skip_items else self._terms(run.terms, by_field, product),
                                             top_k=self._top_k),
            failure=_SEARCH_FAILED, unavailable="법령 품목표의 시행 버전·본문을 확인하지 못해 품목을 대조하지 않았습니다.")
        if candidates is None:
            return []
        query["documents"] = candidates.documents
        definitions = candidates.definitions
        children_source = definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product)

        excluded = by_field.get("excluded_kind", [])
        if excluded:
            kinds = list(dict.fromkeys(_excluded_kind(fact.value) for fact in excluded))
            query["excluded_kind"] = kinds
            run.missing = [name for name in run.missing if name != "target_age"]
            return [self._finding(
                subject="어린이제품 해당 여부 — 제외 물품 가능성",
                summary=(f"어린이제품법 제2조 제1호 단서의 제외 물품({', '.join(kinds)})일 가능성이 있습니다. "
                         "해당하면 어린이제품 안전관리 대상이 아니라 식약 등 다른 법의 검토가 필요합니다. 확정이 아닙니다."),
                rationale="상품 원문에서 제외 물품으로 볼 근거를 찾았습니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=run.facts, assumptions=run.assumptions, sources=[children_source],
            )]

        if state is False:
            return [self._finding(
                subject="어린이제품 해당 여부 — 사용 연령",
                summary="표시된 사용 연령이 만 13세 이하를 포함하지 않아 어린이제품이 아닐 가능성이 있습니다. 확정이 아닙니다.",
                rationale="법 제2조 제1호는 만 13세 이하 어린이가 사용하거나 어린이를 위해 사용되는 물품을 어린이제품으로 봅니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=run.facts, assumptions=run.assumptions, sources=[children_source],
            )]

        if any(name not in by_field for name in _REQUIRED_FIELDS):
            return []

        # 조회 상위 품목에 안전인증·안전확인 품목 전체를 더함. 맞는 품목이 없을 때 공급자적합성확인으로 낮춰 안내하므로,
        # 두 제도의 품목이 조회 순위에서 빠져 모델이 못 본 채로 낮춰지는 일이 없게 함.
        # 순위 밖 품목은 적용범위를 짧게 넣음(전문을 모두 넣으면 입력이 약 4배로 늘었음, 실측)
        ranked = set(candidates.items)
        review_items = list(dict.fromkeys([*candidates.items, *candidates.designated]))
        query["candidate_items"] = [item.item_id for item in review_items]
        findings, chosen = [], []
        if review_items:
            _, review_step = self._get_steps()
            review = review_step.run(ToolStepInput({
                "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in run.facts],
                "age_state": state,
                "candidates": [item.as_candidate() if item in ranked else item.as_candidate(SHORT_SCOPE_LIMIT)
                               for item in review_items],
            }, product.product_id))
            chosen = self._pick(run, review.selections, {item.item_id: item for item in review_items})
            for item, selection, used in chosen:
                run.missing.extend(name for name in selection.needed_fields if name not in by_field)
                action = sale_action(item.scheme, item.name)
                findings.append(self._candidate(item, selection.rationale, used, run, candidates, action))
                run.actions.append(action)
        query["selected_items"] = [item.item_id for item, _, _ in chosen]
        if query["dropped_candidates"]:
            run.assumptions.append(f"후보 행과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")

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
                    facts=run.facts, assumptions=[*run.assumptions, "품목 선택에서 맞는 행을 찾지 못한 결과입니다."],
                    sources=[children_source,
                             definitions.law.source(f"{_LAW_REF} 제12호", definitions.supplier_product),
                             _rule_source(candidates, common)],
                    requirements=[action],
                ))
                run.actions.append(action)
            elif query["dropped_candidates"]:
                run.assumptions.append("품목 선택 결과를 원문·후보와 대조하지 못해 품목을 정하지 않았습니다. "
                                       "안전인증·안전확인 품목일 수 있어 공급자적합성확인으로 낮춰 안내하지 않았습니다.")
            else:
                run.assumptions.append("후보 품목 중 맞는 것을 고르지 못했습니다. 비대상 판단이 아닙니다. "
                                       "만 13세 이하 대상이면 최소한 공급자적합성확인대상입니다(법 제2조 제12호).")
        if findings:
            run.assumptions.append("어린이제품법에서 구매대행 특례 조문을 찾지 못해 구매대행·사입을 나누지 않았습니다.")
        return findings

    @staticmethod
    def _terms(terms: list[str], by_field: dict, product: Product) -> list[str]:
        """조회에 쓸 상품 용어를 모은다.

        Args:
            terms: 모델이 고른 조회어.
            by_field: 필드별 조건.
            product: 검토할 상품.

        Returns:
            list[str]: 조회어 → 제품 종류·용도 값 → 상품명·카테고리·용도 순.
        """
        values = [fact.value for field in ("product_type", "intended_use") for fact in by_field.get(field, [])]
        hints = [value for value in (product.product_name, product.category, product.intended_use) if value]
        return [*terms, *values, *hints]

    def _candidate(self, item: ChildrenItem, rationale: str, used: list[str], run: ChildrenRun,
                   candidates: ChildrenCandidates, action: str) -> RegulatoryFinding:
        """고른 품목 하나의 후보 판단을 만든다.

        Args:
            item: 고른 품목 행.
            rationale: 모델의 선택 이유.
            used: 판단에 쓴 필드.
            run: 이번 실행 상태.
            candidates: 조회 결과 (근거 문서).
            action: 판매 전에 할 일.

        Returns:
            RegulatoryFinding: 어린이제품 대상 후보 판단.
        """
        definitions = candidates.definitions
        sources = [_rule_source(candidates, item)]
        if item.scopes:
            sources.append(_notice_source(candidates, item))
        notes = ["모델 품목 선택이며 규제 적용·인증 보유를 확정하지 않았습니다."]
        summary = (f"이 품목으로 분류되면 {item.scheme.value}대상 어린이제품일 가능성이 있습니다(확정 아님). "
                   f"적용 안전기준: {', '.join(item.standards)}.")
        if run.state is True:
            sources.append(definitions.law.source(f"{_LAW_REF} 제1호", definitions.children_product))
        elif run.state is None:
            summary += " 사용 대상 연령을 확인하지 못했습니다. 만 13세 이하 대상일 때 적용됩니다."
        return self._finding(
            subject=f"{item.scheme.value}대상 어린이제품 후보 — {item.name}", summary=summary, rationale=rationale,
            determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
            facts=[fact for name in used for fact in run.by_field[name]], assumptions=[*run.assumptions, *notes],
            sources=sources, requirements=[action],
        )

    def _detail(self, run: ChildrenRun, findings: list[RegulatoryFinding]) -> ChildrenAssessment:
        """결과에 붙일 어린이제품 상세.

        Args:
            run: 이번 실행 상태.
            findings: 이번 실행의 판단.

        Returns:
            ChildrenAssessment: 연령·제품 종류·제도 요약.
        """
        ages = run.query.get("age_texts") or [fact.value for fact in run.facts if fact.field == "target_age"]
        types = [fact.value for fact in run.facts if fact.field == "product_type"]
        schemes = list(dict.fromkeys(
            finding.subject.split("대상", 1)[0] for finding in findings
            if finding.determination is Determination.POSSIBLY_REQUIRED))
        return ChildrenAssessment(
            target_age_raw=ages[0] if ages else None,
            intended_for_children=run.query.get("age_state"),
            product_type=types[0] if types else None,
            safety_management_required=None,
            certification_type=", ".join(schemes) or None,
            legal_sources=[],
        )


def _excluded_kind(value: str) -> str | None:
    """제외 물품 값을 정해진 이름으로 맞춘다. 공백·가운뎃점(·, ㆍ, ?) 차이는 무시한다.

    Args:
        value: 모델이 낸 제외 물품 값.

    Returns:
        str | None: 정해진 제외 물품 이름. 맞는 것이 없으면 None.
    """
    key = compact(value).translate(_DOTS)
    return next((kind for kind in EXCLUDED_KINDS if compact(kind).translate(_DOTS) == key), None)


def _rule_source(candidates: ChildrenCandidates, item: ChildrenItem) -> LegalSource:
    """품목 행의 시행규칙 별표 근거.

    Args:
        candidates: 조회 결과 (근거 문서).
        item: 품목 행.

    Returns:
        LegalSource: 시행규칙 별표 근거.
    """
    return candidates.rule.source(f"별표 {SCHEME_ANNEXES[item.scheme][0]}", item.row_text)


def _notice_source(candidates: ChildrenCandidates, item: ChildrenItem) -> LegalSource:
    """품목 행의 운용요령 적용범위 근거.

    Args:
        candidates: 조회 결과 (근거 문서).
        item: 적용범위를 이은 품목 행.

    Returns:
        LegalSource: 운용요령 별표 근거.
    """
    return candidates.notice.source(f"별표 {SCHEME_ANNEXES[item.scheme][1]}", " ".join(item.scopes))
