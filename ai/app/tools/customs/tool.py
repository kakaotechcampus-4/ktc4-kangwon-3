"""통관 요건 후보 Tool (#266).

흐름: ① 품목분류 결정 요소 추출(모델, 원문 인용) → ② 결정사례 조회(코드, CLIP) → ③ 같은 물품의 결정사례 선택(모델)
→ ④ HS 후보의 세관장확인 요건 조회(코드, GW) → ⑤ 결과 조립(코드: 관세법·고시 근거, 판매 방식별 할 일).
HS 분류는 관세청이 정하므로 후보로만 낸다. 모델은 확정 판단을 내지 않는다.
결과는 POSSIBLY_REQUIRED(요건 후보) 또는 INSUFFICIENT_INFORMATION(정보 부족·미확인)이다.
"""

from collections.abc import Callable
from typing import Any

from ...prompts import PromptName
from ...schemas.agent import ToolSelectionItem
from ...schemas.customs import CustomsFact, CustomsFacts, CustomsReview
from ...schemas.product import Product
from ...schemas.schemas import (
    CustomsAssessment, Determination, LegalSource, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from ..base import RegulatoryTool
from ..common.agent import ToolModelError, ToolStep, ToolStepInput
from ..common.facts import group_facts, product_snippets, quote_matches
from ..common.law import EvidenceUnavailable
from .evidence import CustomsEvidence, law_key
from .rules import format_hs, omission_status, related_tool, sale_actions
from .search import (
    CaseSearch, HsCase, Requirement, RequirementLookup, default_case_search, default_evidence_loader,
    default_requirement_lookup,
)

_FIELDS = {
    "product_type": "제품 종류", "material": "재질", "function": "기능", "intended_use": "용도",
    "composition": "구성품",
}
# 답에 따라 HS 후보(그리고 요건)가 바뀌는 조건만 묻는다. 나머지는 가정으로 남긴다.
_QUESTION_FIELDS = ("product_type", "material", "function")
# 결정사례 검색어 수. 검색어는 동시에 보내므로 늘려도 대기 시간은 가장 느린 한 건이다.
_QUERY_LIMIT = 6
_SELECTIONS_LIMIT = 3
_CASE_SOURCE = "관세청 품목분류 결정사례(CLIP)"
_TOOL_LABELS = {
    ToolName.ELECTRICAL: "전기안전", ToolName.RADIO: "전파", ToolName.CHILDREN: "어린이제품", ToolName.FOOD_DRUG: "식약",
}


class CustomsToolError(ToolModelError):
    """모델·외부 자료 실패. 원본 오류는 예외 체인에만 보존한다."""


class _FactsStep(ToolStep[CustomsFacts]):
    component_name = "customs-facts"
    prompt_name = PromptName.CUSTOMS_FACTS
    output_schema = CustomsFacts
    error_class = CustomsToolError
    failure_label = "통관 Tool 조건 추출"


class _ReviewStep(ToolStep[CustomsReview]):
    component_name = "customs-review"
    prompt_name = PromptName.CUSTOMS_REVIEW
    output_schema = CustomsReview
    error_class = CustomsToolError
    failure_label = "통관 Tool 결정사례 선택"


class CustomsTool(RegulatoryTool):
    """HS 품목분류 후보와 그 HS의 세관장확인(관세법 제226조) 요건 후보를 찾는다.

    생성 시 설정·모델·API 연결을 만들지 않아 레지스트리 생성 계약을 유지한다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 Tool 프로필(`TOOL_PROFILES`)로 만든다.
        case_search: 결정사례 조회 경로. None이면 CLIP API.
        requirements: HS별 세관장확인 요건 조회 경로. None이면 세관장확인 GW(공공데이터포털 키).
        evidence: 근거 법령을 돌려주는 함수. None이면 법제처 API(기준일별 공용 캐시).
        configured_model: 사용량 기록용 모델 이름.
        top_k: 결정사례 선택 모델에 넘길 후보 수.
    """

    tool_name = ToolName.CUSTOMS

    def __init__(self, model=None, *, case_search: CaseSearch | None = None,
                 requirements: RequirementLookup | None = None,
                 evidence: Callable[[], CustomsEvidence] | None = None,
                 configured_model: str | None = None, top_k: int = 8):
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k는 양의 정수여야 합니다.")
        self._model = model
        self._case_search = case_search
        self._requirements = requirements
        self._evidence = evidence
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
            raise ValueError("통관 Tool과 선택된 Tool 이름이 다릅니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, selected=False, selection_reason=decision.reason,
                              status=ToolStatus.SKIPPED)
        query: dict[str, Any] = {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0}
        snippets = product_snippets(product)
        if not snippets:
            return self._assemble(decision, [], [], ["product_type"], ["입력에 인용 가능한 상품 설명이 없습니다."], query)

        # ① 품목분류 결정 요소 추출
        facts_step, review_step = self._get_steps()
        extracted = facts_step.run(ToolStepInput({"hints": _hints(product), "evidence": snippets}, product.product_id))
        facts = [fact for fact in extracted.facts if quote_matches(fact, snippets)]
        query["dropped_facts"] = len(extracted.facts) - len(facts)
        by_field = group_facts(facts)
        assumptions = ["전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다.",
                       "HS 품목분류는 관세청이 정합니다. 비슷한 결정사례로 찾은 후보이며 확정이 아닙니다."]
        if query["dropped_facts"]:
            assumptions.append(f"원문과 대조되지 않은 상품 조건 {query['dropped_facts']}개를 제외했습니다.")
        if product.conflicts:
            assumptions.append("추출 단계가 상품 정보의 모순을 표시했습니다: " + "; ".join(product.conflicts)
                               + ". 재질·기능과 관련된 모순이면 HS 후보가 달라질 수 있습니다.")
        missing = [field for field in ("product_type",) if field not in by_field]
        if missing:
            return self._assemble(decision, facts, [], missing, assumptions, query)

        # ② 결정사례 조회 (판단 아님)
        product_types = [fact.value for fact in by_field["product_type"]]
        queries = _queries([*(term for term in extracted.search_terms if term.strip()), *product_types])
        terms = [*product_types, *(fact.value for fact in by_field.get("material", [])),
                 *(value for value in (product.product_name, product.category) if value)]
        query["search_terms"] = queries
        try:
            candidates = (self._case_search or default_case_search()).search(queries, terms, top_k=self._top_k)
        except Exception as exc:
            raise CustomsToolError("품목분류 결정사례 조회에 실패했습니다.") from exc
        query["failed_terms"] = list(candidates.failed_terms)
        query["candidate_cases"] = [case.case_id for case in candidates.cases]
        if candidates.failed_terms:
            assumptions.append(f"결정사례 검색어 {len(candidates.failed_terms)}개는 응답을 받지 못해 나머지로 찾았습니다.")
        if not candidates.cases:
            assumptions.append("비슷한 품목분류 결정사례를 찾지 못했습니다. 세관장확인 비대상 판단이 아닙니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)

        # ③ 같은 물품의 결정사례 선택
        review = review_step.run(ToolStepInput({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
            "candidates": [case.as_candidate() for case in candidates.cases],
        }, product.product_id))
        cases = {case.case_id: case for case in candidates.cases}
        chosen: list[tuple[HsCase, str]] = []
        for selection in review.selections:
            if not selection.applies:
                query["not_applicable"] += 1
                continue
            case = cases.get(selection.case_id)
            used = [field for field in dict.fromkeys(selection.fact_fields) if field in by_field]
            if case is None or any(case is picked for picked, _ in chosen) or not used:
                query["dropped_candidates"] += 1
                continue
            if len(chosen) >= _SELECTIONS_LIMIT:
                query["over_limit"] = query.get("over_limit", 0) + 1
                continue
            chosen.append((case, selection.rationale))
            needed = [field for field in dict.fromkeys(selection.needed_fields) if field not in by_field]
            missing.extend(field for field in needed if field in _QUESTION_FIELDS)
            if other := [_FIELDS[field] for field in needed if field not in _QUESTION_FIELDS]:
                assumptions.append(f"HS 확정에는 {', '.join(other)} 확인이 더 필요합니다.")
        query["selected_cases"] = [case.case_id for case, _ in chosen]
        if query["dropped_candidates"]:
            assumptions.append(f"후보 사례와 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        hs_codes = list(dict.fromkeys(code for case, _ in chosen for code in case.hs_codes))
        query["hs_candidates"] = hs_codes
        if not hs_codes:
            assumptions.append("후보 결정사례 중 같은 물품으로 볼 사례를 고르지 못했습니다. 세관장확인 비대상 판단이 아닙니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)

        # ④ 근거 법령과 HS별 세관장확인 요건
        evidence = self._load_evidence(assumptions)
        if evidence is not None:
            query["documents"] = evidence.documents()
        requirements, unresolved = self._lookup(hs_codes, assumptions)
        query["requirements"] = {code: [item.law_name for item in requirements if item.hs_code == code]
                                 for code in hs_codes if code not in unresolved}
        case_sources = [_case_source(case) for case, _ in chosen]
        rationale = " ".join(text for _, text in chosen)

        # ⑤ 결과 조립: 법령별 요건 후보와 판매 방식별 할 일
        findings, actions = [], []
        # GW가 같은 법령에 요건 종류를 붙여 줄 때가 있어(예: "…법률(허가)") 비교 키로 묶는다. 표시는 처음 온 이름.
        by_law: dict[str, list[Requirement]] = {}
        for item in requirements:
            by_law.setdefault(law_key(item.law_name), []).append(item)
        related: dict[str, str] = {}
        for items in by_law.values():
            law_name = items[0].law_name
            codes = list(dict.fromkeys(item.hs_code for item in items))
            documents = list(dict.fromkeys(item.document for item in items if item.document))
            agencies = list(dict.fromkeys(item.agency for item in items if item.agency))
            row = evidence.row_for(law_name) if evidence is not None else None
            # 법령명을 별표 2와 대응하지 못했으면 단서 목록과의 대조도 믿을 수 없다. "생략 가능"으로 잘못 안내하지 않게 확인 필요로 둔다.
            omission = (omission_status(law_name, evidence.omission_exceptions)
                        if evidence is not None and row is not None else None)
            law_actions = sale_actions(law_name, codes, row, documents, agencies, omission)
            actions.extend(law_actions)
            tool = related_tool(law_name)
            notes = ["결정사례 선택은 모델 판단이며 품목분류·요건 적용을 확정하지 않았습니다."]
            if tool is not None:
                related[law_name] = tool.value
                notes.append(f"같은 법의 제품 판단은 {_TOOL_LABELS.get(tool, tool.value)} Tool 결과와 함께 봐야 합니다.")
            findings.append(RegulatoryFinding(
                tool_name=self.tool_name, subject=f"세관장확인 대상 후보 — {law_name}",
                determination=Determination.POSSIBLY_REQUIRED, risk_level=RiskLevel.MEDIUM,
                summary=(f"HS {', '.join(format_hs(code) for code in codes)}로 분류되면 수입통관 때 「{law_name}」 요건을 "
                         f"세관장에게 확인받아야 할 가능성이 있습니다(확정 아님)."
                         + (f" 제출 서류: {', '.join(documents)}." if documents else "")),
                rationale=rationale,
                legal_sources=self._sources(evidence, row, omission, case_sources),
                requirements=law_actions,
                product_facts_used=_facts_used(facts),
                assumptions=[*assumptions, *notes],
            ))
        query["related_tools"] = related
        # 조회는 됐지만 요건이 0건인 HS. 다른 HS에 요건이 있어도 따로 알린다(결과 서술에서 빠지지 않게).
        empty = [code for code in hs_codes if code not in unresolved and not query["requirements"].get(code)]
        if empty:
            act_source = self._act_source(evidence)
            labels = ", ".join(format_hs(code) for code in empty)
            notes = [f"HS 후보({labels}) 기준입니다. 다른 HS로 분류되면 세관장확인 요건이 생길 수 있습니다.",
                     "통관 단계의 요건 확인이 없다는 뜻이며 국내 판매 규제(제품 안전·전파·식품 등)가 없다는 뜻은 아닙니다."]
            if act_source:
                # 조회해서 받은 "요건 없음"은 정보 부족이 아니다. 근거 조문을 붙여 #315 표시·광고 Tool의 "주장 없음"과 같이 낸다.
                findings.append(self._finding(
                    subject="세관장확인 대상 법령 — HS 후보 기준 없음",
                    summary=(f"관세청 세관장확인대상물품 조회 결과 HS 후보 {labels}에는 세관장확인 대상 법령이 "
                             "없습니다. 통관 단계의 요건 확인이 없다는 뜻이며 국내 판매 규제가 없다는 뜻은 아닙니다."),
                    rationale=rationale, determination=Determination.NOT_REQUIRED, risk=RiskLevel.LOW,
                    facts=facts, assumptions=[*assumptions, *notes], sources=[*act_source, *case_sources],
                ))
            else:
                # 근거 법령을 읽지 못하면 확정 판단에 붙일 인용이 없어 정보 부족으로 둔다.
                findings.append(self._finding(
                    subject="세관장확인 대상 법령 — 조회되지 않음",
                    summary=(f"HS 후보 {labels}에는 세관장확인 대상 법령이 조회되지 않았습니다. "
                             "근거 법령을 확인하지 못해 단정하지 않습니다."),
                    rationale=rationale, determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.LOW,
                    facts=facts, assumptions=[*assumptions, *notes], sources=case_sources,
                ))
        if unresolved:
            findings.append(self._finding(
                subject="세관장확인 요건 — 조회하지 못함",
                summary=(f"HS 후보 {', '.join(format_hs(code) for code in unresolved)}의 세관장확인 요건을 조회하지 "
                         "못했습니다. 통관 전 관세청 UNI-PASS의 세관장확인대상 조회로 확인이 필요합니다."),
                rationale=rationale, determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=assumptions, sources=case_sources,
            ))
            actions.append(f"[HS {', '.join(format_hs(code) for code in unresolved)} 후보] 수입 전 관세청 UNI-PASS "
                           "세관장확인대상 조회 또는 관세사를 통해 HS 분류와 요건을 확인해야 합니다.")
        return self._assemble(decision, facts, findings, missing, assumptions, query, actions,
                              hs_codes=hs_codes, requirements=requirements)

    def _load_evidence(self, assumptions: list[str]) -> CustomsEvidence | None:
        try:
            return (self._evidence or default_evidence_loader())()
        except EvidenceUnavailable:
            assumptions.append("관세법·세관장확인 고시의 시행 버전·본문을 확인하지 못해 근거 조문 없이 안내했습니다.")
            return None
        except Exception as exc:
            raise CustomsToolError("통관 근거 법령 조회에 실패했습니다.") from exc

    def _lookup(self, hs_codes: list[str], assumptions: list[str]) -> tuple[list[Requirement], list[str]]:
        """HS 10자리마다 세관장확인 요건을 조회한다. 6자리 HS와 조회할 수 없는 경우는 미확인으로 돌려준다."""
        lookup = self._requirements or default_requirement_lookup()
        requirements: list[Requirement] = []
        unresolved: list[str] = []
        for code in hs_codes:
            if len(code) != 10:
                unresolved.append(code)
                continue
            try:
                requirements.extend(lookup.lookup(code))
            except EvidenceUnavailable as exc:
                unresolved.append(code)
                if str(exc) not in assumptions:
                    assumptions.append(str(exc))
            except Exception as exc:
                raise CustomsToolError("세관장확인 요건 조회에 실패했습니다.") from exc
        if any(len(code) != 10 for code in hs_codes):
            assumptions.append("6단위까지만 결정된 HS는 세관장확인 요건을 조회할 수 없습니다(10단위 필요).")
        return requirements, unresolved

    @staticmethod
    def _act_source(evidence: CustomsEvidence | None) -> list[LegalSource] | None:
        if evidence is None:
            return None
        return [evidence.act.source("제226조", evidence.act_article)]

    def _sources(self, evidence: CustomsEvidence | None, row, omission, case_sources: list[LegalSource]
                 ) -> list[LegalSource]:
        sources = list(self._act_source(evidence) or [])
        if evidence is not None:
            if row is not None:
                sources.append(evidence.notice.source(f"별표 2 ({row.number})", row.text))
            if omission is not None:
                sources.append(evidence.notice.source("제7조", evidence.notice_article))
                sources.append(evidence.decree.source("제19조", evidence.decree_article))
        return [*sources, *case_sources]

    def _finding(self, *, subject: str, summary: str, rationale: str, determination: Determination,
                 risk: RiskLevel, facts: list[CustomsFact], assumptions: list[str],
                 sources: list[LegalSource]) -> RegulatoryFinding:
        return RegulatoryFinding(
            tool_name=self.tool_name, subject=subject, determination=determination, risk_level=risk,
            summary=summary, rationale=rationale, legal_sources=sources,
            product_facts_used=_facts_used(facts), assumptions=list(assumptions),
        )

    def _assemble(self, decision: ToolSelectionItem, facts: list[CustomsFact], findings: list[RegulatoryFinding],
                  missing: list[str], assumptions: list[str], query: dict[str, Any],
                  actions: list[str] | None = None, *, hs_codes: list[str] | None = None,
                  requirements: list[Requirement] | None = None) -> ToolResult:
        missing = list(dict.fromkeys(missing))
        if not findings:
            findings = [self._finding(
                subject="HS 품목분류·세관장확인 요건",
                summary="HS 후보와 세관장확인 요건을 판단하기 위한 정보·결정사례 대응이 부족합니다.",
                rationale="조건 부족 또는 결정사례와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=assumptions, sources=[],
            )]
        requirements = requirements or []
        detail = CustomsAssessment(
            hs_code_candidates=[format_hs(code) for code in hs_codes or []],
            customs_confirmation_required=None,
            applicable_requirements=list(dict.fromkeys(item.law_name for item in requirements)),
            required_documents=list(dict.fromkeys(item.document for item in requirements if item.document)),
            legal_sources=[],
        )
        return ToolResult(
            tool_name=self.tool_name, selected=True, selection_reason=decision.reason,
            status=ToolStatus.SUCCESS, result=detail, findings=findings,
            required_actions=list(dict.fromkeys(actions or [])),
            missing_information=[f"{_FIELDS[field]} 정보가 필요합니다." for field in missing],
            query=query,
        )


def _queries(terms: list[str]) -> list[str]:
    """결정사례 검색어. CLIP은 검색어를 구절 그대로 찾아 두 낱말 이상이면 결과가 거의 없다(실측).

    그래서 여러 낱말 검색어는 마지막 낱말(중심 명사)도 함께 찾는다. 상품별 동의어 사전은 두지 않는다.
    """
    ordered: list[str] = []
    for query in (" ".join(term.split()) for term in terms if term.strip()):
        ordered.append(query)
        # 중심 명사를 그 검색어 바로 뒤에 둔다. 뒤에 몰아 두면 개수 제한에 먼저 잘린다(결과가 나오는 쪽이 잘림).
        words = query.split()
        if len(words) > 1 and len(words[-1]) > 1:
            ordered.append(words[-1])
    return list(dict.fromkeys(ordered))[:_QUERY_LIMIT]


def _facts_used(facts: list[CustomsFact]) -> list[str]:
    return [f"{_FIELDS[fact.field]}: {fact.value} (근거: {fact.quote})" for fact in facts]


def _case_source(case: HsCase) -> LegalSource:
    """결정사례를 근거로 붙인다. 공개 열람 주소가 없어 URL은 비운다(확정 판단 근거로 쓰지 않는다)."""
    codes = ", ".join(format_hs(code) for code in case.hs_codes)
    return LegalSource(
        source_name=_CASE_SOURCE, law_name=None, article=f"결정사례 {case.case_id} (HS {codes})",
        quoted_text=f"{case.product_name} — {case.decision_reason[:200]}", source_url=None,
        effective_date=case.enforce_date, is_mock=False,
    )


def _hints(product: Product) -> dict[str, Any]:
    """조건 추출 모델에 주는 참고값. 판단 근거가 아니며 인용은 evidence에서만 한다.

    원문(listing_text)은 evidence에 이미 있어 빼고, 속성은 이름·값만 남긴다(원문 없는 속성도 조회어를 정하는 데 참고된다).
    """
    hints = product.model_dump(mode="json", exclude={"listing_text", "attributes", "source_url"}, exclude_none=True)
    if product.attributes:
        hints["attributes"] = [{"name": attr.name, "value": attr.value} for attr in product.attributes]
    return hints
