"""통관 요건 후보 Tool (#266).

흐름: ① 품목분류 결정 요소 추출(모델, 원문 인용) → ② 결정사례 조회(코드, CLIP) → ③ 같은 물품의 결정사례 선택(모델)
→ ④ HS 후보의 세관장확인 요건 조회(코드, GW) → ⑤ 결과 조립(코드: 관세법·고시 근거, 판매 방식별 할 일).
HS 분류는 관세청이 정하므로 후보로만 낸다. 모델은 확정 판단을 내지 않는다.
결과는 POSSIBLY_REQUIRED(요건 후보) 또는 INSUFFICIENT_INFORMATION(정보 부족·미확인)이다.
"""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ...schemas.schemas import CustomsAssessment, Determination, LegalSource, RegulatoryFinding, RiskLevel, ToolName
from ..base import EvidenceSearchTool, ToolRun, ToolStepInput
from ..common.law import EvidenceUnavailable
from .errors import CustomsToolError
from .evidence import CustomsEvidence, law_key
from .rules import format_hs, omission_status, related_tool, sale_actions
from .search import (
    CaseSearch, HsCase, Requirement, RequirementLookup,
)
from .steps import CustomsFactsStep, CustomsReviewStep

_FIELDS = {
    "product_type": "제품 종류", "material": "재질", "function": "기능", "intended_use": "용도",
    "composition": "구성품",
}
# 답에 따라 HS 후보(그리고 요건)가 바뀌는 조건만 묻는다. 나머지는 가정으로 남긴다.
_QUESTION_FIELDS = ("product_type", "material", "function")
# 결정사례 검색어 수. 검색어는 동시에 보내므로 늘려도 대기 시간은 가장 느린 한 건이다.
_QUERY_LIMIT = 6
_CASE_SOURCE = "관세청 품목분류 결정사례(CLIP)"
_TOOL_LABELS = {
    ToolName.ELECTRICAL: "전기안전", ToolName.RADIO: "전파", ToolName.CHILDREN: "어린이제품", ToolName.FOOD_DRUG: "식약",
}


@dataclass
class CustomsRun(ToolRun):
    """통관 Tool 실행 상태. 결과 상세에 쓸 HS 후보·요건을 더 가짐.

    Attributes:
        hs_codes: 고른 결정사례의 HS 후보.
        requirements: HS 후보의 세관장확인 요건.
    """

    hs_codes: list[str] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)


class CustomsTool(EvidenceSearchTool):
    """HS 품목분류 후보와 그 HS의 세관장확인(관세법 제226조) 요건 후보를 찾는다.

    생성 시 설정·모델·API 연결을 만들지 않아 레지스트리 생성 계약을 유지한다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 Tool 프로필(`TOOL_PROFILES`)로 만든다.
        case_search: 결정사례 조회 경로.
        requirements: HS별 세관장확인 요건 조회 경로.
        evidence: 근거 법령을 돌려주는 함수.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 결정사례 선택 모델에 넘길 후보 수.
    """

    tool_name = ToolName.CUSTOMS
    facts_step = CustomsFactsStep
    review_step = CustomsReviewStep
    error_class = CustomsToolError
    field_labels = _FIELDS
    empty_fields = ("product_type",)
    base_assumptions = ("HS 품목분류는 관세청이 정합니다. 비슷한 결정사례로 찾은 후보이며 확정이 아닙니다.",)
    conflict_note = ". 재질·기능과 관련된 모순이면 HS 후보가 달라질 수 있습니다."
    insufficient = (
        "HS 품목분류·세관장확인 요건",
        "HS 후보와 세관장확인 요건을 판단하기 위한 정보·결정사례 대응이 부족합니다.",
        "조건 부족 또는 결정사례와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
    )
    # 원문 없는 속성도 조회어를 정하는 데 참고됨
    hints_with_attributes = True
    run_class = CustomsRun

    def __init__(self, model=None, *, case_search: CaseSearch, requirements: RequirementLookup,
                 evidence: Callable[[], CustomsEvidence], configured_model: str | None = None, top_k: int = 8):
        super().__init__(model, configured_model=configured_model, top_k=top_k)
        self._case_search = case_search
        self._requirements = requirements
        self._evidence = evidence

    def _read_facts(self, run: CustomsRun) -> None:
        """제품 종류가 없으면 부족한 조건으로 기록한다.

        Args:
            run: 이번 실행 상태.
        """
        run.missing = [name for name in ("product_type",) if name not in run.by_field]

    def _judge(self, run: CustomsRun) -> list[RegulatoryFinding]:
        """결정사례 조회 → 결정사례 선택 → 세관장확인 요건 조회 → 법령별 요건 후보.

        Args:
            run: 이번 실행 상태.

        Returns:
            list[RegulatoryFinding]: 법령별 요건 후보와 미확인 HS 안내. 근거가 부족하면 빈 목록.

        Raises:
            CustomsToolError: 결정사례 조회나 요건 조회에 실패한 경우.
        """
        product, by_field, query, facts = run.product, run.by_field, run.query, run.facts
        if run.missing:
            return []

        # ① 결정사례 조회 (판단 아님)
        product_types = [fact.value for fact in by_field["product_type"]]
        queries = _queries([*(term for term in run.extracted.search_terms if term.strip()), *product_types])
        terms = [*product_types, *(fact.value for fact in by_field.get("material", [])),
                 *(value for value in (product.product_name, product.category) if value)]
        query["search_terms"] = queries
        try:
            candidates = self._case_search.search(queries, terms, top_k=self._top_k)
        except Exception as exc:
            raise CustomsToolError("품목분류 결정사례 조회에 실패했습니다.") from exc
        query["failed_terms"] = list(candidates.failed_terms)
        query["candidate_cases"] = [case.case_id for case in candidates.cases]
        if candidates.failed_terms:
            run.assumptions.append(f"결정사례 검색어 {len(candidates.failed_terms)}개는 응답을 받지 못해 나머지로 찾았습니다.")
        if not candidates.cases:
            run.assumptions.append("비슷한 품목분류 결정사례를 찾지 못했습니다. 세관장확인 비대상 판단이 아닙니다.")
            return []

        # ② 같은 물품의 결정사례 선택
        _, review_step = self._get_steps()
        review = review_step.run(ToolStepInput({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
            "candidates": [case.as_candidate() for case in candidates.cases],
        }, product.product_id))
        by_id = {case.case_id: case for case in candidates.cases}
        chosen = self._pick(run, review.selections, by_id, key="case_id")
        chosen, lone = _drop_lone_headings(chosen, candidates.cases)
        if lone:
            query["lone_cases"] = lone
            codes = ", ".join(dict.fromkeys(format_hs(code) for case_id in lone for code in by_id[case_id].hs_codes))
            run.assumptions.append(f"후보 사례 중 한 건뿐인 호(HS 4자리)의 선택 {len(lone)}개(HS {codes})를 제외했습니다.")
        for _, selection, _ in chosen:
            needed = [name for name in dict.fromkeys(selection.needed_fields) if name not in by_field]
            run.missing.extend(name for name in needed if name in _QUESTION_FIELDS)
            if other := [_FIELDS[name] for name in needed if name not in _QUESTION_FIELDS]:
                run.assumptions.append(f"HS 확정에는 {', '.join(other)} 확인이 더 필요합니다.")
        query["selected_cases"] = [case.case_id for case, _, _ in chosen]
        if query["dropped_candidates"]:
            run.assumptions.append(f"후보 사례와 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        hs_codes = run.hs_codes = list(dict.fromkeys(code for case, _, _ in chosen for code in case.hs_codes))
        query["hs_candidates"] = hs_codes
        if not hs_codes:
            run.assumptions.append("후보 결정사례 중 같은 물품으로 볼 사례를 고르지 못했습니다. "
                                   "세관장확인 비대상 판단이 아닙니다.")
            return []

        # ③ 근거 법령과 HS별 세관장확인 요건
        evidence = self._lookup(
            run, self._evidence, failure="통관 근거 법령 조회에 실패했습니다.",
            unavailable="관세법·세관장확인 고시의 시행 버전·본문을 확인하지 못해 근거 조문 없이 안내했습니다.")
        if evidence is not None:
            query["documents"] = evidence.documents()
        requirements, unresolved = self._lookup_requirements(hs_codes, run.assumptions)
        run.requirements = requirements
        query["requirements"] = {code: [item.law_name for item in requirements if item.hs_code == code]
                                 for code in hs_codes if code not in unresolved}
        case_sources = [_case_source(case) for case, _, _ in chosen]
        rationale = " ".join(selection.rationale for _, selection, _ in chosen)

        # ④ 법령별 요건 후보와 판매 방식별 할 일
        findings = []
        # GW가 같은 법령에 요건 종류를 붙여 줄 때가 있어(예: "…법률(허가)") 비교 키로 묶음. 표시는 처음 온 이름
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
            # 법령명을 별표 2와 대응하지 못했으면 단서 목록과의 대조도 믿을 수 없음. "생략 가능"으로 잘못 안내하지 않게 확인 필요로 둠
            omission = (omission_status(law_name, evidence.omission_exceptions)
                        if evidence is not None and row is not None else None)
            law_actions = sale_actions(law_name, codes, row, documents, agencies, omission)
            run.actions.extend(law_actions)
            tool = related_tool(law_name)
            notes = ["결정사례 선택은 모델 판단이며 품목분류·요건 적용을 확정하지 않았습니다."]
            if tool is not None:
                related[law_name] = tool.value
                notes.append(f"같은 법의 제품 판단은 {_TOOL_LABELS.get(tool, tool.value)} Tool 결과와 함께 봐야 합니다.")
            findings.append(self._finding(
                subject=f"세관장확인 대상 후보 — {law_name}",
                summary=(f"HS {', '.join(format_hs(code) for code in codes)}로 분류되면 수입통관 때 「{law_name}」 요건을 "
                         f"세관장에게 확인받아야 할 가능성이 있습니다(확정 아님)."
                         + (f" 제출 서류: {', '.join(documents)}." if documents else "")),
                rationale=rationale, determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                facts=facts, assumptions=[*run.assumptions, *notes],
                sources=self._sources(evidence, row, omission, case_sources), requirements=law_actions,
            ))
        query["related_tools"] = related
        # 조회는 됐지만 요건이 0건인 HS. 다른 HS에 요건이 있어도 따로 알림(결과 서술에서 빠지지 않게)
        empty = [code for code in hs_codes if code not in unresolved and not query["requirements"].get(code)]
        if empty:
            act_source = self._act_source(evidence)
            labels = ", ".join(format_hs(code) for code in empty)
            notes = [f"HS 후보({labels}) 기준입니다. 다른 HS로 분류되면 세관장확인 요건이 생길 수 있습니다.",
                     "통관 단계의 요건 확인이 없다는 뜻이며 국내 판매 규제(제품 안전·전파·식품 등)가 없다는 뜻은 아닙니다."]
            if act_source:
                # 조회해서 받은 "요건 없음"은 정보 부족이 아님. 근거 조문을 붙여 #315 표시·광고 Tool의 "주장 없음"과 같이 냄
                findings.append(self._finding(
                    subject="세관장확인 대상 법령 — HS 후보 기준 없음",
                    summary=(f"관세청 세관장확인대상물품 조회 결과 HS 후보 {labels}에는 세관장확인 대상 법령이 "
                             "없습니다. 통관 단계의 요건 확인이 없다는 뜻이며 국내 판매 규제가 없다는 뜻은 아닙니다."),
                    rationale=rationale, determination=Determination.NOT_REQUIRED, risk=RiskLevel.LOW,
                    facts=facts, assumptions=[*run.assumptions, *notes], sources=[*act_source, *case_sources],
                ))
            else:
                # 근거 법령을 읽지 못하면 확정 판단에 붙일 인용이 없어 정보 부족으로 둠
                findings.append(self._finding(
                    subject="세관장확인 대상 법령 — 조회되지 않음",
                    summary=(f"HS 후보 {labels}에는 세관장확인 대상 법령이 조회되지 않았습니다. "
                             "근거 법령을 확인하지 못해 단정하지 않습니다."),
                    rationale=rationale, determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.LOW,
                    facts=facts, assumptions=[*run.assumptions, *notes], sources=case_sources,
                ))
        if unresolved:
            findings.append(self._finding(
                subject="세관장확인 요건 — 조회하지 못함",
                summary=(f"HS 후보 {', '.join(format_hs(code) for code in unresolved)}의 세관장확인 요건을 조회하지 "
                         "못했습니다. 통관 전 관세청 UNI-PASS의 세관장확인대상 조회로 확인이 필요합니다."),
                rationale=rationale, determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=facts, assumptions=run.assumptions, sources=case_sources,
            ))
            run.actions.append(f"[HS {', '.join(format_hs(code) for code in unresolved)} 후보] 수입 전 관세청 UNI-PASS "
                               "세관장확인대상 조회 또는 관세사를 통해 HS 분류와 요건을 확인해야 합니다.")
        return findings

    def _lookup_requirements(self, hs_codes: list[str], assumptions: list[str]
                             ) -> tuple[list[Requirement], list[str]]:
        """HS 10자리마다 세관장확인 요건을 조회한다. 6자리 HS와 조회할 수 없는 경우는 미확인으로 돌려준다.

        Args:
            hs_codes: 고른 결정사례의 HS.
            assumptions: 결과에 남길 가정. 조회할 수 없던 이유를 여기에 더함.

        Returns:
            tuple[list[Requirement], list[str]]: (요건, 미확인 HS).

        Raises:
            CustomsToolError: 요건 조회에 실패한 경우.
        """
        requirements: list[Requirement] = []
        unresolved: list[str] = []
        for code in hs_codes:
            if len(code) != 10:
                unresolved.append(code)
                continue
            try:
                requirements.extend(self._requirements.lookup(code))
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
        """관세법 제226조 근거.

        Args:
            evidence: 통관 근거. 확인하지 못했으면 None.

        Returns:
            list[LegalSource] | None: 근거 한 건. 근거가 없으면 None.
        """
        if evidence is None:
            return None
        return [evidence.act.source("제226조", evidence.act_article)]

    def _sources(self, evidence: CustomsEvidence | None, row, omission, case_sources: list[LegalSource]
                 ) -> list[LegalSource]:
        """요건 법령 하나의 근거를 모은다.

        Args:
            evidence: 통관 근거. 확인하지 못했으면 None.
            row: 고시 별표 2의 해당 행. 없으면 None.
            omission: 고시 제7조 제2항의 생략 판단. 없으면 None.
            case_sources: 결정사례 근거.

        Returns:
            list[LegalSource]: 관세법·고시·대외무역법 시행령·결정사례 순.
        """
        sources = list(self._act_source(evidence) or [])
        if evidence is not None:
            if row is not None:
                sources.append(evidence.notice.source(f"별표 2 ({row.number})", row.text))
            if omission is not None:
                sources.append(evidence.notice.source("제7조", evidence.notice_article))
                sources.append(evidence.decree.source("제19조", evidence.decree_article))
        return [*sources, *case_sources]

    def _detail(self, run: CustomsRun, findings: list[RegulatoryFinding]) -> CustomsAssessment:
        """결과에 붙일 통관 상세.

        Args:
            run: 이번 실행 상태.
            findings: 이번 실행의 판단.

        Returns:
            CustomsAssessment: HS 후보·요건 법령·서류 요약.
        """
        return CustomsAssessment(
            hs_code_candidates=[format_hs(code) for code in run.hs_codes],
            customs_confirmation_required=None,
            applicable_requirements=list(dict.fromkeys(item.law_name for item in run.requirements)),
            required_documents=list(dict.fromkeys(item.document for item in run.requirements if item.document)),
            legal_sources=[],
        )


def _queries(terms: list[str]) -> list[str]:
    """결정사례 검색어. CLIP은 검색어를 구절 그대로 찾아 두 낱말 이상이면 결과가 거의 없다(실측).

    그래서 여러 낱말 검색어는 마지막 낱말(중심 명사)도 함께 찾는다. 상품별 동의어 사전은 두지 않는다.

    Args:
        terms: 조회어와 제품 종류.

    Returns:
        list[str]: 중복을 뺀 검색어 (개수 제한까지).
    """
    ordered: list[str] = []
    for query in (" ".join(term.split()) for term in terms if term.strip()):
        ordered.append(query)
        # 중심 명사를 그 검색어 바로 뒤에 둔다. 뒤에 몰아 두면 개수 제한에 먼저 잘린다(결과가 나오는 쪽이 잘림).
        words = query.split()
        if len(words) > 1 and len(words[-1]) > 1:
            ordered.append(words[-1])
    return list(dict.fromkeys(ordered))[:_QUERY_LIMIT]


def _drop_lone_headings(chosen: list, cases: Iterable[HsCase]) -> tuple[list, list[str]]:
    """고른 사례 중 후보 사례에 한 번만 나온 호(HS 4자리)의 사례를 뺀다. 여러 번 나온 호의 사례를 함께 골랐을 때만.

    Args:
        chosen: _pick이 남긴 (사례, 선택, 근거 필드) 목록.
        cases: 선택 모델에 보여 준 후보 사례 전체.

    Returns:
        tuple[list, list[str]]: 남긴 선택, 뺀 사례 ID.
    """
    support = Counter(heading for case in cases for heading in {code[:4] for code in case.hs_codes})

    def score(case: HsCase) -> int:
        return max((support[code[:4]] for code in case.hs_codes), default=0)

    if all(score(case) <= 1 for case, _, _ in chosen):
        return chosen, []
    return ([item for item in chosen if score(item[0]) > 1],
            [case.case_id for case, _, _ in chosen if score(case) <= 1])


def _case_source(case: HsCase) -> LegalSource:
    """결정사례를 근거로 붙인다. 공개 열람 주소가 없어 URL은 비운다(확정 판단 근거로 쓰지 않는다).

    Args:
        case: 고른 결정사례.

    Returns:
        LegalSource: 결정사례 근거.
    """
    codes = ", ".join(format_hs(code) for code in case.hs_codes)
    return LegalSource(
        source_name=_CASE_SOURCE, law_name=None, article=f"결정사례 {case.case_id} (HS {codes})",
        quoted_text=f"{case.product_name} — {case.decision_reason[:200]}", source_url=None,
        effective_date=case.enforce_date, is_mock=False,
    )
