"""전기안전 Tool: 조건 추출(LLM) → 품목 조회(코드) → 저전압 규칙(코드) → 품목 선택(LLM) → 결과 조립(코드).

법령 원문 전체를 모델에 넣지 않는다. 품목표에서 상품과 비슷한 행 몇 개만 조회해 그중 맞는 행을 고르게 한다.
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
확정은 사람이 검토한 코드 규칙으로만 낸다(아직 없음).
"""

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage

from ..base import RegulatoryTool
from .evidence import EvidenceSection, EvidenceUnavailable, compact, purchase_agent_status
from .rules import (
    BATTERY_SEARCH_TERMS, ESS_WORDS, PURCHASE_SUMMARY, battery_only_state, excluded_by_low_voltage,
    is_battery_or_supply, is_ess_component, item_name, low_voltage, mentions_battery, normal_text, sale_actions,
)
from .search import ElectricalItemSearch, default_item_search
from ...config import build_chat_model
from ...schemas.agent import ToolSelectionItem
from ...schemas.base import StrictModel
from ...schemas.electrical import ElectricalFact, ElectricalFacts, ElectricalReview
from ...schemas.product import Product
from ...schemas.schemas import (
    Determination, ElectricalAssessment, LegalSource, RegulatoryFinding, RiskLevel,
    ToolName, ToolResult, ToolStatus,
)
from ...usage import from_response, record

_PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
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
_Output = TypeVar("_Output", bound=StrictModel)


class ElectricalToolError(RuntimeError):
    """모델·외부 자료 실패. 원본 오류는 예외 체인에만 보존한다."""


class StructuredModel(Protocol):
    def invoke(self, messages: list) -> dict[str, Any]: ...


class ModelLike(Protocol):
    def with_structured_output(self, schema: type, *, include_raw: bool) -> StructuredModel: ...


_QUESTIONS = {
    "battery_only": "제품이 건전지·충전지로만 동작하나요, 아니면 전원 코드·어댑터를 꽂아 쓰나요?",
}


def _legal_source(section: EvidenceSection) -> LegalSource:
    return LegalSource(
        source_name="국가법령정보센터", law_name=section.document_name, article=section.section,
        quoted_text=section.text, source_url=section.source_url, effective_date=section.effective_date,
        is_mock=False,
    )


class ElectricalTool(RegulatoryTool):
    """특정 상품에 고정하지 않는 전기용품 검토.

    생성 시 설정·모델·API 연결을 만들지 않아 레지스트리 생성 계약을 유지한다.
    model과 item_search를 주입하면 네트워크 없는 테스트를 작성할 수 있다.
    """

    tool_name = ToolName.ELECTRICAL

    def __init__(self, model: ModelLike | None = None, *, item_search: ElectricalItemSearch | None = None,
                 configured_model: str | None = None, top_k: int = 8):
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k는 양의 정수여야 합니다.")
        self._model = model
        self._search = item_search
        self._configured_model = configured_model
        self._top_k = top_k

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """미선택은 조회 없이 생략한다. 모델·자료 조회 실패는 예외로 전파해 Executor가 기록한다."""
        if decision.tool_name is not self.tool_name:
            raise ValueError("전기 Tool과 선택된 Tool 이름이 다릅니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, selected=False, selection_reason=decision.reason,
                              status=ToolStatus.SKIPPED)
        snippets = {f"listing-{i}": text for i, text in enumerate(product.listing_text) if text.strip()}
        snippets.update({f"attribute-{i}": attr.source_text for i, attr in enumerate(product.attributes)
                         if attr.source_text and attr.source_text.strip()})
        query: dict[str, Any] = {"dropped_facts": 0, "dropped_candidates": 0}
        if not snippets:
            return self._assemble(decision, [], [], [*_REQUIRED_FIELDS, *_ASKED_FIELDS],
                                  ["입력에 인용 가능한 상품 설명이 없습니다."], query)

        # ① 조건 추출
        model = self._model if self._model is not None else build_chat_model()
        payload = {"hints": product.model_dump(mode="json"), "evidence": snippets}
        extracted: ElectricalFacts = self._invoke(model, ElectricalFacts, "electrical/facts.md", payload, product)
        # 원문과 대조되지 않는 조건은 그 항목만 버린다. 하나 때문에 전체를 실패시키면
        # Verification이 재실행을 반복하고, 대조된 나머지 조건까지 잃는다.
        facts = [fact for fact in extracted.facts if self._fact_matches(fact, snippets.get(fact.evidence_id))]
        query["dropped_facts"] = len(extracted.facts) - len(facts)
        by_field: dict[str, list[ElectricalFact]] = {}
        for fact in facts:
            by_field.setdefault(fact.field, []).append(fact)
        # 같은 값의 중복은 허용하지만 서로 다른 값을 임의로 선택하지 않는다.
        conflicted = [field for field, values in by_field.items() if len({normal_text(f.value) for f in values}) > 1]
        missing = [field for field in (*_REQUIRED_FIELDS, *_ASKED_FIELDS) if field not in by_field]
        missing.extend(conflicted)
        assumptions = ["전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다."]
        if product.conflicts or conflicted:
            assumptions.append("상품 정보에 모순이 있어 적용 조건을 확정하지 않았습니다.")
        if query["dropped_facts"]:
            assumptions.append(f"원문과 대조되지 않은 상품 조건 {query['dropped_facts']}개를 제외했습니다.")
        if any(field not in by_field or field in conflicted for field in _REQUIRED_FIELDS) or product.conflicts:
            result = self._assemble(decision, facts, [], missing, assumptions, query)
            if product.conflicts:
                result.missing_information.append("상품 설명의 모순을 해소할 추가 자료가 필요합니다.")
            return result

        # ② 품목 조회 (판단 아님)
        terms = [term for term in extracted.search_terms if term.strip()]
        terms += [f.value for field in ("product_type", "intended_use", "power_source") for f in by_field.get(field, [])]
        terms += [value for value in (product.product_name, product.category, product.intended_use) if value]
        query["search_terms"] = list(extracted.search_terms)
        try:
            candidates = (self._search or default_item_search()).search(terms, top_k=self._top_k)
        except EvidenceUnavailable:
            assumptions.append("법령 품목표의 시행 버전·본문을 확인하지 못해 품목을 대조하지 않았습니다.")
            return self._assemble(decision, facts, [], missing, assumptions, query)
        except Exception as exc:
            raise ElectricalToolError("전기안전 법령 품목표 조회에 실패했습니다.") from exc
        query["documents"] = candidates.documents
        query["candidate_items"] = [block.block_id for block in candidates.blocks]

        # ③ 명확한 조건은 코드가 판정한다: 운용요령 제3조 저전압 제외
        low, current = low_voltage(by_field) if not ({"power_source", "rated_voltage"} & set(conflicted)) else (None, None)
        query["low_voltage"] = low
        # 전기저장장치(ESS) 구성품 행은 전지라는 단어 때문에 소비자용 배터리에 자주 잘못 붙는다(반복 실측).
        # 상품 원문에 전기저장장치 용도가 없으면 후보에서 뺀다.
        ess_terms = compact(" ".join(f.value + f.quote for f in facts))
        shortlisted = [block for block in candidates.blocks
                       if not is_ess_component(block) or any(word in ess_terms for word in ESS_WORDS)]
        query["filtered_items"] = [block.block_id for block in candidates.blocks if block not in shortlisted]
        # 표 끝 공통 비고: 1차·2차 전지만을 전원으로 사용하는 구조는 각 제도 대상에서 제외한다.
        # 전지로만 동작한다고 원문이 분명하면 본체 행을 빼고 전지·충전기·전원장치 행만 남긴다.
        battery_only = battery_only_state(by_field) if "battery_only" not in conflicted else None
        query["battery_only"] = battery_only
        if battery_only is True:
            kept = [block for block in shortlisted if is_battery_or_supply(block)]
            query["battery_only_excluded"] = [block.block_id for block in shortlisted if block not in kept]
            # 본체 행이 빠지면 검토할 것은 내장 전지와 충전기다. 상품명으로는 이 행들이 잘 조회되지 않아 따로 찾는다.
            try:
                extra = (self._search or default_item_search()).search(list(BATTERY_SEARCH_TERMS), top_k=self._top_k)
            except Exception as exc:
                raise ElectricalToolError("전기안전 법령 품목표 조회에 실패했습니다.") from exc
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
            assumptions.append("상품과 비슷한 품목표 행을 찾지 못했습니다. 비대상 판단이 아닙니다.")
            missing = self._skip_electrical_questions(missing, by_field, assumptions)
            return self._assemble(decision, facts, [], missing, assumptions, query)

        # ④ 품목 선택
        review: ElectricalReview = self._invoke(model, ElectricalReview, "electrical/review.md", {
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
            "low_voltage": low, "battery_only": battery_only,
            "common_notes": {scheme.value: note.text for scheme, note in candidates.common_notes.items()},
            "candidates": rows,
        }, product)

        # ⑤ 결과 조립: 근거는 코드가 행 원문으로 붙인다
        blocks = {block.block_id: block for block in shortlisted}
        findings, selected, actions = [], [], []
        query["purchase_agent"] = {}
        battery_hint = battery_only is None and mentions_battery(by_field, product)
        for selection in review.selections:
            block = blocks.get(selection.item_id)
            # 확인되지 않은 조건을 근거로 든 부분은 무시하고, 확인된 조건이 하나도 없을 때만 선택을 버린다.
            used_fields = [field for field in dict.fromkeys(selection.fact_fields) if field in by_field]
            if (block is None or selection.item_id in selected or excluded_by_low_voltage(block, low, current)
                    or not used_fields):
                query["dropped_candidates"] += 1
                continue
            selected.append(selection.item_id)
            missing.extend(field for field in selection.needed_fields if field not in by_field)
            sources = [_legal_source(block.section)]
            notes = ["LLM 품목 선택이며 규제 적용·인증 보유를 확정하지 않았습니다."]
            if low is True:
                sources.append(_legal_source(candidates.notice_scope))
            scheme = block.scheme.value
            # 전지 사용이 보이는데 전지 전용인지 모르면, 본체 후보에 공통 비고의 제외 가능성을 붙이고 묻는다.
            if battery_hint and not is_battery_or_supply(block):
                missing.append("battery_only")
                notes.append(f"전지(건전지·충전지)만으로 동작하는 구조라면 본체는 {scheme}대상에서 제외됩니다"
                             "(운용요령 별표 공통 비고).")
                if block.scheme in candidates.common_notes:
                    sources.append(_legal_source(candidates.common_notes[block.scheme]))
            # ⑦ 구매대행 특례(법 제35조, 시행규칙 별표 13)와 판매 전 해야 할 일
            part = candidates.purchase_agent.get(block.scheme)
            status, listed_as = purchase_agent_status(block, part)
            query["purchase_agent"][selection.item_id] = status
            if part is not None and status != "unknown":
                sources.append(_legal_source(part))
            actions.extend(sale_actions(block, status, listed_as))
            findings.append(RegulatoryFinding(
                tool_name=self.tool_name, subject=f"{scheme}대상 후보 — {item_name(block)}",
                determination=Determination.POSSIBLY_REQUIRED, risk_level=RiskLevel.MEDIUM,
                summary=f"{scheme}대상 전기용품일 가능성이 높습니다. {PURCHASE_SUMMARY[status]}",
                rationale=selection.rationale, legal_sources=sources,
                product_facts_used=[f"{_FIELDS[field]}: {f.value} (근거: {f.quote})"
                                    for field in used_fields for f in by_field[field]],
                assumptions=[*assumptions, *notes],
            ))
        query["selected_items"] = selected
        if query["dropped_candidates"]:
            assumptions.append(f"후보 행과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        if not findings:
            assumptions.append("후보 행 중 상품에 맞는 품목을 고르지 못했습니다. 비대상 판단이 아닙니다.")
            if battery_only is True:
                assumptions.append("전지로만 동작하는 구조라 본체는 공통 비고에 따라 제외될 수 있습니다. 확정이 아닙니다.")
            missing = self._skip_electrical_questions(missing, by_field, assumptions)
        return self._assemble(decision, facts, findings, missing, assumptions, query, actions)

    @staticmethod
    def _skip_electrical_questions(missing: list[str], by_field: dict, assumptions: list[str]) -> list[str]:
        """맞는 품목도, 전기 관련 조건도 없는 상품(예: 실리콘 주걱)에는 전원·전압을 묻지 않는다."""
        if any(field in by_field for field in _ELECTRICAL_FIELDS):
            return missing
        assumptions.append("상품 원문에 전기 관련 조건이 없어 전원·전압을 묻지 않았습니다.")
        return [field for field in missing if field not in _ASKED_FIELDS]

    @staticmethod
    def _fact_matches(fact: ElectricalFact, source: str | None) -> bool:
        """값이 인용 안에, 인용이 지정한 상품 원문 안에 그대로 있는지.

        battery_only만 값이 "예"/"아니오"이고, 인용은 그 판단의 원문 근거다.
        """
        if source is None or not normal_text(fact.quote) or normal_text(fact.quote) not in normal_text(source):
            return False
        if fact.field == "battery_only":
            return fact.value.strip() in ("예", "아니오")
        return bool(normal_text(fact.value)) and normal_text(fact.value) in normal_text(fact.quote)

    def _invoke(self, model: ModelLike, schema: type[_Output], prompt_name: str,
                payload: dict, product: Product) -> _Output:
        started = perf_counter()
        raw = None
        error = None
        try:
            response = model.with_structured_output(schema, include_raw=True).invoke([
                SystemMessage(content=(_PROMPTS / prompt_name).read_text(encoding="utf-8")),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ])
            raw = response.get("raw")
            if response.get("parsing_error") is not None or not isinstance(response.get("parsed"), schema):
                raise ElectricalToolError("전기 Tool 구조화 출력을 읽을 수 없습니다.")
            return response["parsed"]
        except Exception as exc:
            error = type(exc).__name__
            raise ElectricalToolError("전기 Tool 모델 처리에 실패했습니다.") from exc
        finally:
            record("electrical-facts" if schema is ElectricalFacts else "electrical-review", from_response(raw),
                   configured_model=self._configured_model or getattr(model, "model_name", None),
                   subject_id=product.product_id, ok=error is None,
                   elapsed_ms=round((perf_counter() - started) * 1000), error_type=error)

    def _assemble(self, decision: ToolSelectionItem, facts: list[ElectricalFact],
                  findings: list[RegulatoryFinding], missing: list[str], assumptions: list[str],
                  query: dict[str, Any], actions: list[str] | None = None) -> ToolResult:
        missing = list(dict.fromkeys(missing))
        if not findings:
            findings = [RegulatoryFinding(
                tool_name=self.tool_name, subject="전기용품 안전관리 대상 판정",
                determination=Determination.INSUFFICIENT_INFORMATION, risk_level=RiskLevel.UNKNOWN,
                summary="규제 적용을 판단하기 위한 정보·품목 대응이 부족합니다.",
                rationale="조건 부족·모순 또는 품목표와의 대응이 미확인입니다. 빈 후보를 비대상 근거로 사용하지 않습니다.",
                product_facts_used=[f"{_FIELDS[f.field]}: {f.value} (근거: {f.quote})" for f in facts],
                assumptions=assumptions,
            )]
        detail = ElectricalAssessment(
            power_sources=list(dict.fromkeys(f.value for f in facts if f.field == "power_source")),
            rated_specifications=list(dict.fromkeys(f.value for f in facts if f.field == "rated_voltage")),
            # 후보만으로 상품 전체의 안전관리 의무를 확정하지 않는다.
            # 긴 근거는 findings에만 둔다(Verification 입력에 같은 원문이 두 번 들어가지 않게).
            safety_management_required=None, legal_sources=[],
        )
        return ToolResult(
            tool_name=self.tool_name, selected=True, selection_reason=decision.reason,
            status=ToolStatus.SUCCESS, result=detail, findings=findings,
            required_actions=list(dict.fromkeys(actions or [])),
            missing_information=[_QUESTIONS.get(field, f"{_FIELDS[field]} 정보가 필요합니다.") for field in missing],
            # 버린 수·조회 후보·저전압 판정. 흔들림 측정과 운영 디버깅에 쓴다.
            query=query,
        )
