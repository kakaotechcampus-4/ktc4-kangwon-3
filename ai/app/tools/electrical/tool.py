"""전기안전 Tool: 조건 추출(LLM) → 품목 조회(코드) → 저전압 규칙(코드) → 품목 선택(LLM) → 결과 조립(코드).

법령 원문 전체를 모델에 넣지 않는다. 품목표에서 상품과 비슷한 행 몇 개만 조회해 그중 맞는 행을 고르게 한다.
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
확정은 사람이 검토한 코드 규칙으로만 낸다(아직 없음).
"""

from ..base import EvidenceSearchTool, ToolRun, ToolStepInput
from ..common.facts import quote_matches
from .errors import ElectricalToolError
from .evidence import compact, purchase_agent_status
from .rules import (
    BATTERY_SEARCH_TERMS, ESS_WORDS, PURCHASE_SUMMARY, battery_only_state, excluded_by_low_voltage,
    is_battery_or_supply, is_ess_component, item_name, low_voltage, mentions_battery, power_conflicts, sale_actions,
)
from .search import ElectricalItemSearch, default_item_search
from .steps import ElectricalFactsStep, ElectricalReviewStep
from ...schemas.electrical import ElectricalFact
from ...schemas.schemas import Determination, ElectricalAssessment, RegulatoryFinding, RiskLevel, ToolName

_FIELDS = {
    "product_type": "제품 종류", "power_source": "전원 방식", "rated_voltage": "정격 전압",
    "intended_use": "제품 용도", "battery_only": "배터리 전용 여부",
    "adapter_included": "어댑터 포함 여부", "rated_power": "정격 소비전력",
}
# 품목 조회에는 제품 종류만 있으면 된다. 전원·전압이 없으면 질문으로 남기고 검토는 계속한다.
_REQUIRED_FIELDS = ("product_type",)
_ASKED_FIELDS = ("power_source", "rated_voltage")
# 상품이 전기를 쓴다는 원문 근거가 되는 조건.
_ELECTRICAL_FIELDS = ("power_source", "rated_voltage", "rated_power", "battery_only", "adapter_included")
# 답에 따라 코드 판단이 바뀌는 조건(품목 조회·저전압 제외·전지 전용 제외)만 사용자에게 묻는다.
# 모델이 확정에 더 필요하다고 한 나머지 조건은 질문이 아니라 가정으로 남긴다.
_QUESTION_FIELDS = ("product_type", "power_source", "rated_voltage", "battery_only")
# 값이 판단 결과("예"/"아니오")라 인용 안에 그대로 있지 않아도 되는 조건.
_JUDGED_FIELDS = ("battery_only",)

_QUESTIONS = {
    "battery_only": "제품이 건전지·충전지로만 동작하나요, 아니면 전원 코드·어댑터를 꽂아 쓰나요?",
}
_SEARCH_FAILED = "전기안전 법령 품목표 조회에 실패했습니다."


class ElectricalTool(EvidenceSearchTool):
    """특정 상품에 고정하지 않는 전기용품 검토.

    생성 시 설정·모델·API 연결을 만들지 않아 레지스트리 생성 계약을 유지한다.
    model과 item_search를 주입하면 네트워크 없는 테스트를 작성할 수 있다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 설정으로 만든다.
        item_search: 품목 조회 경로. None이면 법제처 API 경로(프로세스 공용 캐시)를 쓴다.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 품목 선택 모델에 넘길 후보 행 수.
    """

    tool_name = ToolName.ELECTRICAL
    facts_step = ElectricalFactsStep
    review_step = ElectricalReviewStep
    error_class = ElectricalToolError
    field_labels = _FIELDS
    questions = _QUESTIONS
    empty_fields = (*_REQUIRED_FIELDS, *_ASKED_FIELDS)
    conflict_note = ". 제품 종류·전원과 관련된 모순이면 결과가 달라질 수 있습니다."
    insufficient = (
        "전기용품 안전관리 대상 판정",
        "규제 적용을 판단하기 위한 정보·품목 대응이 부족합니다.",
        "조건 부족·모순 또는 품목표와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
    )
    tracks_conflicts = True
    # 원문 없는 속성도 조회어를 정하는 데 참고됨
    hints_with_attributes = True

    def __init__(self, model=None, *, item_search: ElectricalItemSearch | None = None,
                 configured_model: str | None = None, top_k: int = 8):
        super().__init__(model, configured_model=configured_model, top_k=top_k)
        self._search = item_search

    def _item_search(self) -> ElectricalItemSearch:
        return self._search or default_item_search()

    def _fact_matches(self, fact: ElectricalFact, run: ToolRun) -> bool:
        """인용이 지정한 상품 원문 안에, 값이 인용 안에 그대로 있는지.

        battery_only만 값이 "예"/"아니오"이고, 인용은 그 판단의 원문 근거다.
        """
        if fact.field in _JUDGED_FIELDS:
            return fact.value.strip() in ("예", "아니오") and quote_matches(fact, run.snippets, value_in_quote=False)
        return quote_matches(fact, run.snippets)

    def _read_facts(self, run: ToolRun) -> None:
        """판단을 바꾸는 조건의 충돌과 부족한 조건을 기록한다."""
        # 판단을 바꾸는 조건만 충돌로 봄. 전원·전압은 글자가 아니라 뜻으로 비교(USB/DC, "0~5V"/"5V"는 같음),
        # 전지 전용 여부는 예·아니오가 함께 나올 때만 충돌. 제품 종류·용도는 값이 여러 개여도 모두 조회어로 씀
        run.conflicted.extend(power_conflicts(run.by_field))
        if len({fact.value.strip() for fact in run.by_field.get("battery_only", [])}) > 1:
            run.conflicted.append("battery_only")
        run.missing = [name for name in (*_REQUIRED_FIELDS, *_ASKED_FIELDS) if name not in run.by_field]
        run.missing.extend(run.conflicted)
        if run.conflicted:
            run.assumptions.append("상품 정보에 모순이 있어 해당 조건(" + ", ".join(_FIELDS[f] for f in run.conflicted)
                                   + ")은 판정하지 않았습니다.")

    def _judge(self, run: ToolRun) -> list[RegulatoryFinding]:
        """품목 조회 → 저전압·전지 전용 규칙 → 품목 선택 → 후보 판단."""
        product, by_field, query = run.product, run.by_field, run.query
        if any(name not in by_field for name in _REQUIRED_FIELDS):
            return []

        # ① 품목 조회 (판단 아님)
        terms = [term for term in run.extracted.search_terms if term.strip()]
        terms += [f.value for name in ("product_type", "intended_use", "power_source") for f in by_field.get(name, [])]
        terms += [value for value in (product.product_name, product.category, product.intended_use) if value]
        query["search_terms"] = list(run.extracted.search_terms)
        candidates = self._lookup(
            run, lambda: self._item_search().search(terms, top_k=self._top_k), failure=_SEARCH_FAILED,
            unavailable="법령 품목표의 시행 버전·본문을 확인하지 못해 품목을 대조하지 않았습니다.")
        if candidates is None:
            return []
        query["documents"] = candidates.documents
        query["candidate_items"] = [block.block_id for block in candidates.blocks]

        # ② 명확한 조건은 코드가 판정: 운용요령 제3조 저전압 제외
        power_conflicted = {"power_source", "rated_voltage"} & set(run.conflicted)
        low, current = low_voltage(by_field) if not power_conflicted else (None, None)
        query["low_voltage"] = low
        # 전기저장장치(ESS) 구성품 행은 전지라는 단어 때문에 소비자용 배터리에 자주 잘못 붙음(반복 실측).
        # 상품 원문에 전기저장장치 용도가 없으면 후보에서 뺌
        ess_terms = compact(" ".join(f.value + f.quote for f in run.facts))
        shortlisted = [block for block in candidates.blocks
                       if not is_ess_component(block) or any(word in ess_terms for word in ESS_WORDS)]
        query["filtered_items"] = [block.block_id for block in candidates.blocks if block not in shortlisted]
        # 표 끝 공통 비고: 1차·2차 전지만을 전원으로 사용하는 구조는 각 제도 대상에서 제외.
        # 전지로만 동작한다고 원문이 분명하면 본체 행을 빼고 전지·충전기·전원장치 행만 남김
        battery_only = battery_only_state(by_field) if "battery_only" not in run.conflicted else None
        query["battery_only"] = battery_only
        if battery_only is True:
            kept = [block for block in shortlisted if is_battery_or_supply(block)]
            query["battery_only_excluded"] = [block.block_id for block in shortlisted if block not in kept]
            # 본체 행이 빠지면 검토할 것은 내장 전지와 충전기. 상품명으로는 이 행들이 잘 조회되지 않아 따로 찾음
            try:
                extra = self._item_search().search(list(BATTERY_SEARCH_TERMS), top_k=self._top_k)
            except Exception as exc:
                raise ElectricalToolError(_SEARCH_FAILED) from exc
            for block in extra.blocks:
                if (is_battery_or_supply(block) and not is_ess_component(block)
                        and block.block_id not in {b.block_id for b in kept}):
                    kept.append(block)
            shortlisted = kept
            query["candidate_items"] = list(dict.fromkeys(
                [*query["candidate_items"], *(block.block_id for block in shortlisted)]))
        rows = [{
            "item_id": block.block_id, "scheme": block.scheme.value, "category": block.category,
            "item": item_name(block), "sub_items": list(block.sub_items), "notes": list(block.notes),
            "low_voltage_excluded": excluded_by_low_voltage(block, low, current),
        } for block in shortlisted]
        if not rows:
            run.assumptions.append("상품과 비슷한 품목표 행을 찾지 못했습니다. 비대상 판단이 아닙니다.")
            self._skip_electrical_questions(run)
            return []

        # ③ 품목 선택
        _, review_step = self._get_steps()
        review = review_step.run(ToolStepInput({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in run.facts],
            "low_voltage": low, "battery_only": battery_only,
            "common_notes": {scheme.value: note.text for scheme, note in candidates.common_notes.items()},
            "candidates": rows,
        }, product.product_id))

        # ④ 후보 판단: 근거는 코드가 행 원문으로 붙임
        query["purchase_agent"] = {}
        battery_hint = battery_only is None and mentions_battery(by_field, product)
        chosen = self._pick(run, review.selections, {block.block_id: block for block in shortlisted}, limit=None,
                            skip=lambda block: excluded_by_low_voltage(block, low, current))
        findings = []
        for block, selection, used in chosen:
            needed = [name for name in dict.fromkeys(selection.needed_fields) if name not in by_field]
            run.missing.extend(name for name in needed if name in _QUESTION_FIELDS)
            sources = [block.section.source()]
            notes = ["LLM 품목 선택이며 규제 적용·인증 보유를 확정하지 않았습니다."]
            if other := [_FIELDS[name] for name in needed if name not in _QUESTION_FIELDS]:
                notes.append(f"품목 확정에는 {', '.join(other)} 확인이 더 필요합니다.")
            if low is True:
                sources.append(candidates.notice_scope.source())
            scheme = block.scheme.value
            # 전지 사용이 보이는데 전지 전용인지 모르면, 본체 후보에 공통 비고의 제외 가능성을 붙이고 물음
            if battery_hint and not is_battery_or_supply(block):
                run.missing.append("battery_only")
                notes.append(f"전지(건전지·충전지)만으로 동작하는 구조라면 본체는 {scheme}대상에서 제외됩니다"
                             "(운용요령 별표 공통 비고).")
                if block.scheme in candidates.common_notes:
                    sources.append(candidates.common_notes[block.scheme].source())
            # 구매대행 특례(법 제35조, 시행규칙 별표 13)와 판매 전 해야 할 일
            part = candidates.purchase_agent.get(block.scheme)
            status, listed_as = purchase_agent_status(block, part)
            query["purchase_agent"][selection.item_id] = status
            if part is not None and status != "unknown":
                sources.append(part.source())
            block_actions = sale_actions(block, status, listed_as)
            run.actions.extend(block_actions)
            # requirements: 재실행에서 이 판단이 빠지면 ToolExecutor가 이 판단의 할 일만 함께 지울 수 있게 연결
            findings.append(self._finding(
                subject=f"{scheme}대상 후보 — {item_name(block)}",
                summary=f"이 품목으로 분류되면 {scheme}대상 전기용품일 가능성이 있습니다(확정 아님). "
                        f"{PURCHASE_SUMMARY[status]}",
                rationale=selection.rationale, determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                facts=[f for name in used for f in by_field[name]], assumptions=[*run.assumptions, *notes],
                sources=sources, requirements=block_actions,
            ))
        query["selected_items"] = [selection.item_id for _, selection, _ in chosen]
        if query["dropped_candidates"]:
            run.assumptions.append(f"후보 행과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        if not findings:
            run.assumptions.append("후보 행 중 상품에 맞는 품목을 고르지 못했습니다. 비대상 판단이 아닙니다.")
            if battery_only is True:
                run.assumptions.append("전지로만 동작하는 구조라 본체는 공통 비고에 따라 제외될 수 있습니다. 확정이 아닙니다.")
            self._skip_electrical_questions(run)
        return findings

    @staticmethod
    def _skip_electrical_questions(run: ToolRun) -> None:
        """맞는 품목도, 전기 관련 조건도 없는 상품(예: 실리콘 주걱)에는 전원·전압을 묻지 않는다."""
        if any(name in run.by_field for name in _ELECTRICAL_FIELDS):
            return
        run.assumptions.append("상품 원문에 전기 관련 조건이 없어 전원·전압을 묻지 않았습니다.")
        run.missing = [name for name in run.missing if name not in _ASKED_FIELDS]

    def _detail(self, run: ToolRun, findings: list[RegulatoryFinding]) -> ElectricalAssessment:
        # 후보만으로 상품 전체의 안전관리 의무를 확정하지 않음.
        # 긴 근거는 findings에만 둠(Verification 입력에 같은 원문이 두 번 들어가지 않게)
        return ElectricalAssessment(
            power_sources=list(dict.fromkeys(f.value for f in run.facts if f.field == "power_source")),
            rated_specifications=list(dict.fromkeys(f.value for f in run.facts if f.field == "rated_voltage")),
            safety_management_required=None, legal_sources=[],
        )
