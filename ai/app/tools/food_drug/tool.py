"""식약 안전 후보 Tool (#266) — 식품용 기구·용기 / 식품·건강기능식품 / 화장품 / 의료기기.

흐름: ① 조건 추출(모델: 음식 접촉·먹는 것·바르는 것 판단 + 원문 근거, 효능 문구·성분 인용, 기능성 범위 대응)
→ ② 영역별 규칙(코드: 판단에 법 조문·할 일을 붙임. 화장품 성분은 사용할 수 없는 원료와 이름 대조)
→ ③ 의료기기 품목 조회(코드) → ④ 품목 선택(모델) → ⑤ 결과 조립(코드).
"이게 화장품인가" 같은 해당 여부는 모델이 원문 근거로 판단하고, 코드는 그 판단에 법 조문·할 일을 붙인다.
제품 분류만 본다. 광고 문구 자체의 위법 가능성은 표시·광고 Tool(#295)이 맡는다.
모델은 확정 판단을 내지 않는다. 결과는 POSSIBLY_REQUIRED(후보) 또는 INSUFFICIENT_INFORMATION(정보 부족)이다.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ...schemas.food_drug import FoodDrugFact, FoodDrugFacts
from ...schemas.product import Product
from ...schemas.schemas import Determination, FoodDrugAssessment, LegalSource, RegulatoryFinding, RiskLevel, ToolName
from ..base import EvidenceSearchTool, ToolRun, ToolStepInput
from ..base.evidence_search import SELECTIONS_LIMIT
from ..common.facts import quote_matches
from .errors import FoodDrugToolError
from .evidence import DeviceItem, FoodDrugEvidence
from .rules import (
    banned_action, claim_action, cosmetic_actions, device_actions, functional_action, health_food_action,
    imported_food_actions,
)
from .search import rank_devices
from .steps import FoodDrugFactsStep, FoodDrugReviewStep

_FIELDS = {
    "product_type": "제품 종류", "material": "재질", "intended_use": "용도", "food_contact": "음식 접촉 용도",
    "edible": "먹는 것 여부", "skin_applied": "바르는 것 여부", "health_claim": "효능 표방 문구",
    "beauty_claim": "피부·모발 효과 문구", "ingredient": "성분",
}
_QUESTIONS = {
    "food_contact": "음식이나 음료에 직접 닿는 용도(먹을 때 쓰거나 담는 것, 조리·보관에 쓰는 것)인가요?",
    "edible": "사람이 먹거나 마시는 제품인가요?",
    "skin_applied": "피부·모발 등 몸에 바르거나 뿌려 쓰는 제품인가요?",
}
# 값이 판단 결과("예"/"아니오")인 조건. 값은 인용 안에 그대로 있지 않아도 된다(인용은 판단의 원문 근거).
_JUDGED_FIELDS = ("food_contact", "edible", "skin_applied")
_TERMS_LIMIT = 3
FOOD_CONTACT, FOOD, COSMETIC, FUNCTIONAL, DEVICE = "식품용 기구·용기", "식품·건강기능식품", "화장품", "기능성화장품", "의료기기"


@dataclass
class FoodDrugRun(ToolRun):
    """식약 Tool 실행 상태. 근거 법령과 해당 영역을 더 가짐.

    Attributes:
        evidence: 식약 근거 법령. 확인하지 못하면 None.
        categories: 후보를 낸 영역 (식품용 기구·식품·화장품·기능성화장품·의료기기).
    """

    evidence: FoodDrugEvidence | None = None
    categories: list[str] = field(default_factory=list)


class FoodDrugTool(EvidenceSearchTool):
    """식품용 기구·식품·건강기능식품(수입신고), 화장품(책임판매업·기능성·금지 원료), 의료기기(수입허가) 후보를 찾는다.

    Args:
        model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 Tool 프로필(`TOOL_PROFILES`)로 만든다.
        evidence: 근거(법령 조문 + 의료기기 품목·등급 + 화장품 금지 원료)를 돌려주는 함수.
        configured_model: 사용량 기록용 모델 이름.
        top_k: 품목 선택 모델에 넘길 의료기기 후보 수.
    """

    tool_name = ToolName.FOOD_DRUG
    facts_step = FoodDrugFactsStep
    review_step = FoodDrugReviewStep
    error_class = FoodDrugToolError
    field_labels = _FIELDS
    questions = _QUESTIONS
    conflict_note = ". 용도·효능과 관련된 모순이면 결과가 달라질 수 있습니다."
    insufficient = (
        "식품·화장품·의료기기 해당 여부",
        "상품 원문에서 음식에 닿거나 먹거나 바르는 쓰임, 질병·신체 기능에 관한 효능 문구를 찾지 못했습니다. 비대상 판단이 아닙니다.",
        "식약 관련 분류로 볼 원문 근거가 없습니다. 근거가 없다는 것을 비대상의 근거로 사용하지 않습니다.",
    )
    # 원문 없는 속성도 조회어를 정하는 데 참고됨
    hints_with_attributes = True
    run_type = FoodDrugRun

    def __init__(self, model=None, *, evidence: Callable[[], FoodDrugEvidence],
                 configured_model: str | None = None, top_k: int = 8):
        super().__init__(model, configured_model=configured_model, top_k=top_k)
        self._evidence = evidence

    def _prepare(self, run: FoodDrugRun) -> None:
        """근거를 먼저 읽는다. 기능성화장품 범위(시행규칙 제2조)를 조건 추출 모델에 함께 줌."""
        run.evidence = self._lookup(
            run, self._evidence, failure="식약 근거 법령 조회에 실패했습니다.",
            unavailable="식약 근거 법령의 시행 버전·본문을 확인하지 못해 근거 조문 없이 안내했습니다.")
        if run.evidence is not None:
            run.query["documents"] = run.evidence.documents()

    def _facts_payload(self, run: FoodDrugRun) -> dict[str, Any]:
        functional_types = ([{"number": item.number, "text": item.text} for item in run.evidence.functional_types]
                            if run.evidence is not None else [])
        return {**super()._facts_payload(run), "functional_types": functional_types}

    def _raw_facts(self, run: FoodDrugRun) -> list:
        return [*run.extracted.facts, *_judged_facts(run.extracted)]

    def _fact_matches(self, fact: FoodDrugFact, run: FoodDrugRun) -> bool:
        if fact.field in _JUDGED_FIELDS:
            return fact.value.strip() in ("예", "아니오") and quote_matches(fact, run.snippets, value_in_quote=False)
        return quote_matches(fact, run.snippets)

    def _judge(self, run: FoodDrugRun) -> list[RegulatoryFinding]:
        """판단 칸 상태 → 의료기기 품목 조회·선택 → 영역별 규칙(식품용 기구·식품·화장품)."""
        product, facts, by_field, query = run.product, run.facts, run.by_field, run.query
        evidence, assumptions, categories = run.evidence, run.assumptions, run.categories
        # 모델은 "예"라고 했지만 근거 인용이 원문과 맞지 않아 버린 판단. 답에 따라 판단이 바뀌므로 물음
        unverified = {fact.field for fact in self._raw_facts(run)
                      if fact.field in _JUDGED_FIELDS and fact.value.strip() == "예" and fact not in facts}
        state = {name: self._judged(name, run, name in unverified) for name in _JUDGED_FIELDS}
        query.update(state)
        label = _label(by_field, product)
        findings: list[RegulatoryFinding] = []

        def add(category: str, items: list[RegulatoryFinding], new_actions: list[str]) -> None:
            if items:
                categories.append(category)
                findings.extend(items)
                run.actions.extend(new_actions)

        # 먹거나 바르는 상품의 질병 효능 표방은 의약품 오인 문제라 의료기기 품목으로 보지 않음.
        # 판단은 만들 때의 가정을 복사하므로, 이 안내는 판단을 만들기 전에 남김
        claims = [fact.value for fact in by_field.get("health_claim", [])]
        query["health_claims"] = claims
        ingested_or_applied = state["edible"] is True or state["skin_applied"] is True
        if ingested_or_applied and claims:
            assumptions.append("먹거나 바르는 상품의 질병·신체 기능 효능 문구(" + ", ".join(claims) + ")는 의약품으로 오인될 수 "
                               "있습니다. 표시·광고 Tool 결과와 함께 봐야 합니다.")

        # ③④ 의료기기: 먹거나 바르는 상품이 아니고, 효능 문구가 있거나 품목 명칭이 나왔을 때 품목표를 조회.
        # 다른 영역 판단보다 먼저 실행해, 여기서 남긴 안내(품목 미대응·버린 선택)가 뒤에 만드는 판단에도 들어가게 함
        device_findings: list[RegulatoryFinding] = []
        device_todo: list[str] = []
        if not ingested_or_applied and (claims or any(term.strip() for term in run.extracted.device_terms)):
            device_findings, device_todo = self._devices(run)

        # ② 영역별 규칙: 모델의 판단("예")과 원문 근거가 있을 때만 법 조문·할 일을 붙임
        if state["food_contact"] is True:
            add(FOOD_CONTACT, *self._food_contact(label, facts, by_field, evidence, assumptions))
        if state["edible"] is True:
            add(FOOD, *self._food(label, facts, by_field, evidence, assumptions))
        if state["skin_applied"] is True:
            cosmetic, cosmetic_todo = self._cosmetic(label, facts, by_field, run.extracted, evidence, assumptions,
                                                     query)
            add(COSMETIC, cosmetic, cosmetic_todo)
            if any(finding.subject.startswith(FUNCTIONAL) for finding in cosmetic):
                categories.append(FUNCTIONAL)

        findings.extend(device_findings)
        run.actions.extend(device_todo)
        if any(finding.determination is Determination.POSSIBLY_REQUIRED for finding in device_findings):
            categories.append(DEVICE)
        query["categories"] = categories
        return findings

    @staticmethod
    def _judged(field: str, run: FoodDrugRun, unverified: bool) -> bool | None:
        """판단 칸의 상태. 예·아니오가 엇갈리거나, "예"의 근거를 원문에서 확인하지 못했거나,
        추출 단계만 음식 접촉으로 보고 근거가 없으면 묻는다."""
        values = {fact.value.strip() for fact in run.by_field.get(field, [])}
        if values == {"예", "아니오"}:
            run.missing.append(field)
            run.assumptions.append(f"{_FIELDS[field]}의 원문 근거가 서로 달라 해당 여부를 정하지 않았습니다.")
            return None
        if not values and unverified:
            run.missing.append(field)
            run.assumptions.append(f"{_FIELDS[field]}를 '예'로 볼 원문 근거를 확인하지 못해 해당 여부를 정하지 않았습니다.")
        elif not values and field == "food_contact" and run.product.food_contact is True:
            run.missing.append(field)
        return True if values == {"예"} else False if values == {"아니오"} else None

    def _food_contact(self, label: str, facts: list[FoodDrugFact], by_field: dict,
                      evidence: FoodDrugEvidence | None, assumptions: list[str]):
        notes = ["상품 원문의 쓰임으로 본 후보이며 식품용 기구 해당을 확정하지 않았습니다."]
        if "material" not in by_field:
            notes.append("재질이 확인되지 않아 적용할 기구 기준·규격(재질별)을 정하지 않았습니다.")
        todo = imported_food_actions(label, "식품용 기구")
        sources = [] if evidence is None else [evidence.food_definition.source(), *_import_sources(evidence)]
        return [self._finding(
            subject="식품용 기구·용기 후보 — 수입신고 대상",
            summary=("음식에 직접 닿는 용도로 보여, 식품용 기구(식품위생법 제2조 제4호)라면 판매 목적으로 수입할 때 "
                     "수입신고 대상일 가능성이 있습니다(확정 아님)."),
            rationale="상품 원문에 음식·음료에 직접 닿는 쓰임이 적혀 있습니다: "
                      + "; ".join(f"'{fact.quote}'" for fact in by_field["food_contact"]),
            determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
            facts=facts, assumptions=[*assumptions, *notes], sources=sources, requirements=todo,
        )], todo

    def _food(self, label: str, facts: list[FoodDrugFact], by_field: dict,
              evidence: FoodDrugEvidence | None, assumptions: list[str]):
        """먹거나 마시는 상품. 건강기능식품도 수입식품등이라(수입식품법 제2조 제1호) 수입신고·영업등록은 같다.

        먹는 상품의 효능 문구는 몸 기능이든 피부 효과든(예: "피부 보습에 도움") 건강기능식품 확인 대상이다.
        """
        claims = list(dict.fromkeys(fact.value for field in ("health_claim", "beauty_claim")
                                    for fact in by_field.get(field, [])))
        todo = imported_food_actions(label, "식품")
        summary = ("사람이 먹거나 마시는 상품으로 보여, 식품(식품위생법 제2조 제1호)이라면 판매 목적으로 수입할 때 "
                   "수입신고 대상일 가능성이 있습니다(확정 아님).")
        sources = [] if evidence is None else [evidence.food_item.source(), evidence.imported_scope.source(),
                                               *_import_sources(evidence)]
        if claims:
            summary += (f" 기능성 표방 문구({', '.join(claims)})가 있어 건강기능식품(건강기능식품에 관한 법률 제3조) 해당 여부도 "
                        "확인이 필요합니다.")
            todo = [*todo, health_food_action(label, claims)]
            if evidence is not None:
                sources.insert(1, evidence.health_food.source())
        return [self._finding(
            subject="식품·건강기능식품 후보 — 수입신고 대상",
            summary=summary,
            rationale="상품 원문에 먹거나 마시는 상품이라는 근거가 있습니다: "
                      + "; ".join(f"'{fact.quote}'" for fact in by_field["edible"]),
            determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM, facts=facts,
            assumptions=[*assumptions, "건강기능식품의 인정된 기능성 원료 대조는 하지 않았습니다."],
            sources=sources, requirements=todo,
        )], todo

    def _cosmetic(self, label: str, facts: list[FoodDrugFact], by_field: dict, extracted: FoodDrugFacts,
                  evidence: FoodDrugEvidence | None, assumptions: list[str], query: dict[str, Any]):
        """바르는 상품: 화장품 후보(책임판매업), 기능성 표방(심사·보고), 사용할 수 없는 원료(이름 대조).

        기능성 대응·성분 대조의 안내(notes)를 먼저 계산해 화장품 판단의 가정에 함께 넣는다.
        """
        # 바르는 상품의 효과 문구는 어느 효능 칸에 들어왔든(모델이 미백을 health_claim에 넣는 일이 있다) 기능성 대응의 근거로 쓴다.
        claim_facts = [*by_field.get("beauty_claim", []), *by_field.get("health_claim", [])]
        beauty = list(dict.fromkeys(fact.value for fact in claim_facts))
        ingredients = list(by_field.get("ingredient", []))
        notes = ["의약품(약사법)에 해당하는 물품은 화장품에서 제외됩니다(화장품법 제2조 제1호 단서)."]
        types, matched = [], []
        if evidence is not None:
            # 기능성화장품: 효과 문구가 원문에 있고, 모델이 대응시킨 호가 시행규칙 제2조에 실제로 있을 때만
            types = [item for number in dict.fromkeys(extracted.functional_types)
                     if (item := evidence.functional(number))] if beauty else []
            # 사용할 수 없는 원료: 성분명이 별표 1의 원료명·화학물질명과 같을 때만(글자 대조)
            # 같은 원료를 여러 곳에서 인용해도 판단은 원료 행마다 하나만 낸다.
            matched = list({row.name: (fact, row) for fact in ingredients
                            if (row := evidence.banned_match(fact.value))}.values())
            if beauty and not types:
                notes.append(f"피부·모발 효과 문구({', '.join(beauty)})를 기능성화장품 범위에 대응하지 못했습니다.")
            if not ingredients:
                notes.append("성분 정보가 없어 사용할 수 없는 원료를 대조하지 못했습니다.")
            elif not matched:
                notes.append("성분명 글자 대조에서 사용할 수 없는 원료와 같은 이름이 없었습니다. 다른 이름(영문명·이명)으로 "
                             "적힌 원료는 찾지 못하므로 안전하다는 뜻은 아닙니다.")
        query["functional_types"] = [item.number for item in types]
        query["banned_ingredients"] = [row.name for _, row in matched]

        todo = cosmetic_actions(label)
        findings = [self._finding(
            subject="화장품 후보 — 화장품책임판매업 등록 대상",
            summary=("몸에 바르거나 뿌려 쓰는 상품으로 보여, 화장품(화장품법 제2조 제1호)이라면 수입해 판매하거나 수입대행을 "
                     "알선할 때 화장품책임판매업 등록이 필요할 가능성이 있습니다(확정 아님)."),
            rationale="상품 원문에 몸에 바르거나 뿌려 쓰는 상품이라는 근거가 있습니다: "
                      + "; ".join(f"'{fact.quote}'" for fact in by_field["skin_applied"]),
            determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM, facts=facts,
            assumptions=[*assumptions, *notes],
            sources=[] if evidence is None else [evidence.cosmetic_definition.source(),
                                                 evidence.cosmetic_business_scope.source(),
                                                 evidence.cosmetic_business.source()],
            requirements=todo,
        )]
        if types:
            action = functional_action(label, types)
            todo = [*todo, action]
            findings.append(self._finding(
                subject="기능성화장품 후보 — " + ", ".join(f"시행규칙 제2조 제{item.number}호" for item in types),
                summary=(f"피부·모발 효과 문구({', '.join(beauty)})가 기능성화장품 범위에 해당할 수 있습니다(확정 아님). "
                         "기능성화장품으로 판매하려면 품목별 심사 또는 보고서 제출이 필요합니다."),
                rationale="해당할 수 있는 범위: " + " / ".join(f"제{item.number}호 {item.text}" for item in types),
                determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                facts=claim_facts, assumptions=list(assumptions),
                sources=[evidence.functional_definition.source(), *(evidence.functional_scope.doc.source(
                    f"제2조 제{item.number}호", item.text) for item in types), evidence.functional_review.source(),
                         evidence.cosmetic_sale_ban.source()],
                requirements=[action],
            ))
        for fact, row in matched:
            action = banned_action(fact.value, row)
            todo = [*todo, action]
            if row.conditional:
                # 조건이 붙은 행(예: 석면기준에 적합하지 않은 탤크)은 이름이 같아도 조건 확인 전에는 금지라고 할 수 없다.
                subject = f"사용할 수 없는 원료 해당 여부 확인 — {row.name}"
                summary = (f"성분 '{fact.value}'가 「화장품 안전기준 등에 관한 규정」 별표 1의 조건부 금지 원료 '{row.name}'와 "
                           "이름이 겹칩니다. 원료가 이 조건에 해당하면 판매·수입대행 알선이 금지됩니다(화장품법 제15조 제5호). "
                           "조건 해당 여부는 원료 규격서로 확인이 필요합니다.")
                risk = RiskLevel.MEDIUM
            else:
                subject = f"사용할 수 없는 원료 포함 가능성 — {row.name}"
                summary = (f"성분 '{fact.value}'가 「화장품 안전기준 등에 관한 규정」 별표 1의 사용할 수 없는 원료 '{row.name}'와 "
                           "이름이 같습니다. 이 원료를 쓴 화장품은 판매·수입대행 알선이 금지됩니다(화장품법 제15조 제5호). "
                           "성분명 글자 대조 결과이며 확정이 아닙니다.")
                risk = RiskLevel.HIGH
            findings.append(self._finding(
                subject=subject, summary=summary,
                rationale=f"원문 성분 표기: '{fact.quote}'",
                determination=Determination.POSSIBLY_REQUIRED, risk=risk, facts=[fact],
                assumptions=list(assumptions),
                sources=[evidence.cosmetic_ban.source(), evidence.cosmetic_notice.source(),
                         evidence.cosmetic_notice.doc.source("별표 1", row.row_text),
                         evidence.cosmetic_sale_ban.source()],
                requirements=[action],
            ))
        return findings, todo

    def _devices(self, run: FoodDrugRun) -> tuple[list[RegulatoryFinding], list[str]]:
        facts, by_field, evidence = run.facts, run.by_field, run.evidence
        assumptions, query = run.assumptions, run.query
        claims = [fact.value for fact in by_field.get("health_claim", [])]

        def unmatched(reason: str) -> tuple[list[RegulatoryFinding], list[str]]:
            # 효능 문구가 없으면 경고할 대상이 없다. 품목을 못 찾은 사실만 가정으로 남긴다.
            if not claims:
                assumptions.append(f"의료기기 품목과 대응하지 못했습니다: {reason} 비대상 판단이 아닙니다.")
                return [], []
            return [self._unmatched(claims, facts, assumptions, evidence, reason)], [claim_action(claims)]

        if evidence is None:
            return unmatched("의료기기 품목·등급 근거를 확인하지 못해 품목을 대조하지 않았습니다.")
        terms = [term for term in run.extracted.device_terms if term.strip()][:_TERMS_LIMIT]
        terms += [fact.value for field in ("product_type", "intended_use") for fact in by_field.get(field, [])]
        query["device_terms"] = list(run.extracted.device_terms)
        candidates = rank_devices(evidence.devices, terms, top_k=self._top_k) if terms else []
        query["candidate_items"] = [item.item_id for item in candidates]
        if not candidates:
            return unmatched("비슷한 의료기기 품목을 찾지 못했습니다.")
        _, review_step = self._get_steps()
        review = review_step.run(ToolStepInput({
            "facts": [fact.model_dump(mode="json", exclude={"evidence_id"}) for fact in facts],
            "candidates": [item.as_candidate() for item in candidates],
        }, run.product.product_id))
        # 먼저 선택을 대조해 버린 수를 세고, 그 안내를 담아 판단을 만듦(판단은 만들 때의 가정을 복사함)
        chosen = self._pick(run, review.selections, {item.item_id: item for item in candidates})
        query["selected_items"] = [item.item_id for item, _, _ in chosen]
        if query["dropped_candidates"]:
            assumptions.append(f"후보 품목과 대조되지 않은 선택 {query['dropped_candidates']}개를 제외했습니다.")
        if query.get("over_limit"):
            assumptions.append(f"품목 선택이 {SELECTIONS_LIMIT}개를 넘어 {query['over_limit']}개는 쓰지 않았습니다.")
        findings, actions = [], []
        for item, selection, used in chosen:
            needed = [field for field in dict.fromkeys(selection.needed_fields) if field not in by_field]
            # 의료기기 품목을 가르는 조건은 용도뿐이다. 음식 접촉 등 다른 칸은 질문하지 않는다.
            run.missing.extend(field for field in needed if field == "intended_use")
            notes = ["모델 품목 선택이며 의료기기 해당·허가 보유를 확정하지 않았습니다."]
            if other := [_FIELDS[field] for field in needed if field != "intended_use"]:
                notes.append(f"품목 확정에는 {', '.join(other)} 확인이 더 필요합니다.")
            item_actions = device_actions(item)
            actions.extend(item_actions)
            findings.append(self._finding(
                subject=f"의료기기 후보 — {item.name} ({item.grade}등급)",
                summary=(f"이 품목으로 분류되면 의료기기({item.grade}등급)일 가능성이 있습니다(확정 아님). "
                         f"품목 정의: {item.definition}"),
                rationale=selection.rationale, determination=Determination.POSSIBLY_REQUIRED, risk=RiskLevel.MEDIUM,
                facts=[fact for fact in facts if fact.field in used], assumptions=[*assumptions, *notes],
                sources=_device_sources(evidence, item), requirements=item_actions,
            ))
        if not findings:
            reason = ("품목 선택 결과를 후보·원문과 대조하지 못했습니다." if query["dropped_candidates"]
                      else "후보 품목 중 맞는 것을 고르지 못했습니다.")
            return unmatched(reason)
        return findings, actions

    def _unmatched(self, claims: list[str], facts: list[FoodDrugFact], assumptions: list[str],
                   evidence: FoodDrugEvidence | None, reason: str) -> RegulatoryFinding:
        """효능 문구는 있는데 의료기기 품목을 정하지 못한 경우. 비대상 판단이 아니다."""
        sources = [] if evidence is None else [evidence.device_definition.source(), evidence.device_misleading.source()]
        return self._finding(
            subject="의료기기 해당 여부 — 품목 미확인",
            summary=(f"효능 표방 문구({', '.join(claims)})가 있지만 의료기기 품목과 대응하지 못했습니다. "
                     "의료기기라면 수입허가 등이 필요하고, 의료기기가 아니라면 의료기기와 비슷한 효능으로 오인될 "
                     "표시·광고를 할 수 없습니다(의료기기법 제26조 제7항). 비대상 판단이 아닙니다."),
            rationale=reason, determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.MEDIUM,
            facts=facts, assumptions=[*assumptions, "효능 문구 자체의 표시·광고 위반 가능성은 표시·광고 Tool 결과와 함께 봐야 합니다."],
            sources=sources, requirements=[claim_action(claims)],
        )

    def _detail(self, run: FoodDrugRun, findings: list[RegulatoryFinding]) -> FoodDrugAssessment:
        return FoodDrugAssessment(
            regulatory_categories=list(run.categories),
            regulated=None,
            detected_claims=[fact.value for fact in run.facts if fact.field in ("health_claim", "beauty_claim")],
            ingredients_or_materials=list(dict.fromkeys(
                fact.value for fact in run.facts if fact.field in ("material", "ingredient"))),
            applicable_requirements=list(dict.fromkeys(
                source.law_name for finding in findings for source in finding.legal_sources if source.law_name)),
            legal_sources=[],
        )


def _judged_facts(extracted: FoodDrugFacts) -> list[FoodDrugFact]:
    """필수 판단 세 개 중 "모름"이 아닌 것을 조건(값 "예"/"아니오" + 원문 근거)으로 바꾼다."""
    return [FoodDrugFact(field=field, value=judgment.answer, evidence_id=judgment.evidence_id, quote=judgment.quote)
            for field in _JUDGED_FIELDS if (judgment := getattr(extracted.judgments, field)).answer != "모름"]


def _import_sources(evidence: FoodDrugEvidence) -> list[LegalSource]:
    return [evidence.import_business.source(), evidence.import_business_scope.source(),
            evidence.import_registration.source(), evidence.import_report.source()]


def _device_sources(evidence: FoodDrugEvidence, item: DeviceItem) -> list[LegalSource]:
    return [evidence.device_definition.source(), evidence.device_notice.source("별표 1", item.row_text),
            evidence.device_import.source(), evidence.device_sale.source(), evidence.device_unapproved.source(),
            evidence.device_exemption.source()]


def _label(by_field: dict, product: Product) -> str:
    types = [fact.value for fact in by_field.get("product_type", [])]
    return types[0] if types else (product.product_name or "상품")
