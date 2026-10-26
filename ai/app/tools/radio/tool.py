"""방송통신기자재 적합성평가 대상 후보 Tool (#297).

흐름: ① 조건 추출(모델, 원문 인용) → ② 대상기자재 조회(코드) → ③ 규칙(코드: 무선 기능 근거, 주파수 정규화)
→ ④ 기자재 선택(모델) → ⑤ 결과 조립(코드: 행 원문·평가유형·판매 방식별 할 일).
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
"""

from dataclasses import dataclass, field
from typing import Any

from ...schemas.product import Product
from ...schemas.schemas import Determination, RadioAssessment, RegulatoryFinding, RiskLevel, ToolName
from ..base import EvidenceSearchTool, ToolRun, ToolStepInput
from .errors import RadioToolError
from .evidence import RadioItem
from .rules import ASSESSMENT_PARAGRAPH, band_label, normalized_bands, sale_actions
from .search import RadioCandidates, RadioItemSearch
from .steps import RadioFactsStep, RadioReviewStep

_FIELDS = {
    "product_type": "제품 종류", "wireless_feature": "무선 기능", "frequency": "사용 주파수",
    "output_power": "출력", "intended_use": "제품 용도",
}
_QUESTIONS = {
    "wireless_feature": "무선 기능(블루투스·Wi-Fi·무선충전·RF 리모컨 등) 정보가 필요합니다.",
}
_REQUIRED_FIELDS = ("product_type", "wireless_feature")
# 판단을 바꾸는 조건만 질문한다(#341과 같은 기준). 주파수·출력·용도는 선택 모델의 참고값이라 가정으로 남긴다.
_QUESTION_FIELDS = _REQUIRED_FIELDS
_SEARCH_TERMS_LIMIT = 3
_NOTE_LIMIT = 1500
_SEARCH_FAILED = "전파 대상기자재 조회에 실패했습니다."


@dataclass
class RadioRun(ToolRun):
    """전파 Tool 실행 상태.

    Attributes:
        catalog: 대상기자재 분류명 목록 (조건 추출 모델이 조회어를 고를 때 씀).
        terms: 조건 추출 모델이 고른 조회어.
        bands: 상품 원문의 주파수 범위(MHz).
    """

    catalog: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    bands: list[tuple[float, float]] = field(default_factory=list)


class RadioTool(EvidenceSearchTool):
    """방송통신기자재 적합성평가(적합인증·적합등록·자기적합확인) 대상 후보를 찾는다. 무선 기능이 있는 상품만 본다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 설정으로 만든다.
        item_search: 대상기자재 조회 경로.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 기자재 선택 모델에 넘길 후보 행 수.
    """

    tool_name = ToolName.RADIO
    facts_step = RadioFactsStep
    review_step = RadioReviewStep
    error_class = RadioToolError
    field_labels = _FIELDS
    questions = _QUESTIONS
    empty_fields = _REQUIRED_FIELDS
    conflict_note = ". 무선 기능·제품 종류와 관련된 모순이면 결과가 달라질 수 있습니다."
    insufficient = (
        "방송통신기자재 적합성평가 대상 판정",
        "규제 적용을 판단하기 위한 정보·기자재 대응이 부족합니다.",
        "무선 기능 근거 부족·모순 또는 대상기자재와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
    )
    run_type = RadioRun

    def __init__(self, model=None, *, item_search: RadioItemSearch, configured_model: str | None = None,
                 top_k: int = 8):
        super().__init__(model, configured_model=configured_model, top_k=top_k)
        self._search = item_search

    def _prepare(self, run: RadioRun) -> None:
        """대상기자재 분류명 목록을 읽는다. 근거를 확인할 수 없으면 목록 없이 추출."""
        run.catalog = self._lookup(run, self._search.catalog, failure=_SEARCH_FAILED) or []

    def _facts_payload(self, run: RadioRun) -> dict[str, Any]:
        return {**super()._facts_payload(run), "categories": run.catalog}

    def _read_facts(self, run: RadioRun) -> None:
        """조회어와 주파수를 읽고 필수 조건 부족을 기록한다."""
        run.terms = [term for term in run.extracted.search_terms if term.strip()][:_SEARCH_TERMS_LIMIT]
        run.query["search_terms"] = run.terms
        # 주파수가 무선 기능 값 안에만 있는 경우(예: "Bluetooth 5.0 (2.4GHz)")도 읽음
        run.bands = normalized_bands([fact.value for name in ("frequency", "wireless_feature")
                                      for fact in run.by_field.get(name, [])])
        run.query["frequency_bands"] = [band_label(band) for band in run.bands]
        run.missing = [name for name in _REQUIRED_FIELDS if name not in run.by_field]
        if not run.bands:
            run.assumptions.append("상품 원문에서 사용 주파수를 찾지 못해 후보 행의 대역과 대조하지 않았습니다.")

    def _judge(self, run: RadioRun) -> list[RegulatoryFinding]:
        """무선 기능 근거 → 대상기자재 조회 → 기자재 선택 → 후보 판단."""
        by_field = run.by_field
        if "wireless_feature" not in by_field:
            run.assumptions.append("상품 원문에서 무선 기능 근거를 찾지 못해 무선기기 후보를 내지 않았습니다. "
                                   "비대상 판단이 아닙니다(유선 전자파적합성 기기는 이 Tool 범위 밖).")
            return []
        if any(name not in by_field for name in _REQUIRED_FIELDS):
            return []

        candidates = self._lookup(
            run, lambda: self._search.search(self._terms(run.terms, by_field, run.product), top_k=self._top_k),
            failure=_SEARCH_FAILED,
            unavailable="법령 대상기자재의 시행 버전·본문을 확인하지 못해 기자재를 대조하지 않았습니다.")
        if candidates is None:
            return []
        run.query["documents"] = candidates.documents
        run.query["candidate_items"] = [item.item_id for item in candidates.items]
        if not candidates.items:
            run.assumptions.append("상품과 비슷한 대상기자재 행을 찾지 못했습니다. 비대상 판단이 아닙니다.")
            return []

        _, review_step = self._get_steps()
        sections = list(dict.fromkeys(item.section for item in candidates.items))
        review = review_step.run(ToolStepInput({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in run.facts],
            "product_bands_mhz": [list(band) for band in run.bands],
            "section_notes": {section: candidates.section_notes[section][:_NOTE_LIMIT]
                              for section in sections if section in candidates.section_notes},
            "candidates": [item.as_candidate() for item in candidates.items],
        }, run.product.product_id))

        chosen = self._pick(run, review.selections, {item.item_id: item for item in candidates.items})
        findings = []
        for item, selection, used in chosen:
            needed = [name for name in dict.fromkeys(selection.needed_fields) if name not in by_field]
            run.missing.extend(name for name in needed if name in _QUESTION_FIELDS)
            notes = []
            if other := [_FIELDS[name] for name in needed if name not in _QUESTION_FIELDS and name in _FIELDS]:
                notes.append(f"기자재 확정에는 {', '.join(other)} 확인이 더 필요합니다.")
            item_actions = sale_actions(item, candidates.personal_use)
            run.actions.extend(item_actions)
            findings.append(self._candidate(item, selection.rationale, used, by_field, candidates,
                                            [*run.assumptions, *notes], item_actions))
        run.query["selected_items"] = [item.item_id for item, _, _ in chosen]
        run.query["assessment_types"] = list(dict.fromkeys(kind for item, _, _ in chosen for kind in item.assessment))
        if run.query["dropped_candidates"]:
            run.assumptions.append(f"후보 행과 대조되지 않은 선택 {run.query['dropped_candidates']}개를 제외했습니다.")
        if not findings:
            run.assumptions.append("후보 행 중 상품에 맞는 기자재를 고르지 못했습니다. 비대상 판단이 아닙니다.")
        return findings

    @staticmethod
    def _terms(terms: list[str], by_field: dict, product: Product) -> list[str]:
        values = [fact.value for field in ("wireless_feature", "product_type", "intended_use")
                  for fact in by_field.get(field, [])]
        hints = [value for value in (product.product_name, product.category) if value]
        return [*terms, *values, *hints]

    def _candidate(self, item: RadioItem, rationale: str, used: list[str], by_field: dict,
                   candidates: RadioCandidates, assumptions: list[str], actions: list[str]) -> RegulatoryFinding:
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
                     "판매 목적 수입은 판매 전 적합성평가가 필요합니다."
                     + (" 개인 사용 목적 반입은 면제 대상일 수 있습니다(시행령 별표 6의2)."
                        if candidates.personal_use is not None else "")),
            rationale=rationale, legal_sources=sources, requirements=list(actions),
            product_facts_used=[self._fact_line(fact) for field in used for fact in by_field[field]],
            assumptions=[*assumptions, "모델 기자재 선택이며 적합성평가 대상·인증 보유를 확정하지 않았습니다. "
                         "평가유형은 고시 별표 1의 행 표시를 그대로 옮겼습니다."],
        )

    def _detail(self, run: RadioRun, findings: list[RegulatoryFinding]) -> RadioAssessment:
        return RadioAssessment(
            wireless_features=list(dict.fromkeys(fact.value for fact in run.facts if fact.field == "wireless_feature")),
            frequency_bands=list(run.query.get("frequency_bands", [])),
            conformity_assessment_required=None,
            certification_type=", ".join(run.query.get("assessment_types", [])) or None,
            legal_sources=[],
        )
