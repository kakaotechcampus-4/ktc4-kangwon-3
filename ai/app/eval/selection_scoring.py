"""선택 정답표와 N회 선택 결과를 대조한다. LLM을 부르지 않는다.

채점과 "추출 탓 / 선택 탓" 나누기 기준은 docs/SELECTION_EVAL.md 1·2절을 그대로 따른다.
같은 추출 결과를 두 번 쓴다.

- 모드 B: 추출 결과를 그대로 선택에 넣는다. 실제 파이프라인과 같다.
- 모드 A: 같은 추출 결과에서 boolean 필드만 정답값으로 바꿔 넣는다.

두 모드의 입력은 boolean만 다르므로, B에서만 생긴 오류는 추출의 boolean 판단에서 온다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas.agent import ToolSelectionResponse
from ..schemas.schemas import ToolName
from .grading import Grade, Stability, classify_stability, is_hard_flip

# 툴 판단에 쓰는 boolean 필드(SELECTION_EVAL.md 4절). 통관은 거의 항상 선택하고
# 표시광고는 listing_text를 보므로 판단 필드가 없어 탓 나누기에서 뺀다.
JUDGEMENT_FIELDS: dict[ToolName, tuple[str, ...]] = {
    ToolName.RADIO: ("wireless_comm", "wireless_charging", "wireless_shield"),
    ToolName.FOOD_DRUG: ("food_contact", "medical_claim", "cosmetic_claim"),
    ToolName.ELECTRICAL: ("electrical_powered", "battery_included", "battery_is_the_product", "heating"),
    ToolName.CHILDREN: ("for_children",),
}


class Blame:
    """B에서만 생긴 C1이 누구 탓인지(SELECTION_EVAL.md 1절)."""

    # 판단 필드를 근거 없이 false로 확정했다
    EXTRACTION = "추출"
    # 판단 필드는 같은데 다른 boolean이 정답과 달랐다. A·B 입력은 boolean만 다르므로
    # 판단 필드가 같으면 차이는 나머지 boolean에서 온다(power_bank 전파에서 실측)
    EXTRACTION_OTHER = "추출(다른 필드)"
    # 추출은 모른다고(null) 넘겼는데 선택이 "없음"으로 봤다. 원칙 2 위반
    SELECTION = "선택(원칙 2)"
    # boolean 입력이 A와 똑같은데 결과만 달랐다. 같은 입력에서 나오는 흔들림
    NOISE = "선택(흔들림)"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.loads는 같은 키가 두 번 나오면 뒤의 값으로 조용히 덮어쓴다. 손으로 고치다
    # 툴 항목을 복사해 붙이면 앞의 판단이 흔적 없이 사라지므로 여기서 막는다.
    keys = [key for key, _ in pairs]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated:
        raise ValueError(f"같은 키가 두 번 있습니다: {duplicated}")
    return dict(pairs)


def load_selection_truth(path: Path) -> dict:
    """선택 정답표를 읽는다. 6개 툴이 모두 참거짓으로 적혀 있어야 한다."""
    truth = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    tools = truth.get("tools") or {}
    if set(tools) != {name.value for name in ToolName}:
        raise ValueError(f"{path.name}: 6개 툴이 각각 한 번씩 있어야 합니다: {sorted(tools)}")
    if any(not isinstance(spec.get("selected"), bool) for spec in tools.values()):
        raise ValueError(f"{path.name}: selected는 참거짓이어야 합니다")
    return truth


def correct_booleans(product: dict, extraction_truth: dict) -> dict:
    """추출 결과에서 boolean 필드만 정답값으로 바꾼 사본(모드 A 입력)을 만든다.

    정답이 null인 필드도 null로 바꾼다. 페이지에 근거가 없다는 것도 정답이기 때문이다.
    글자 필드(상품명·category·listing_text 등)는 정답표에 입력으로 쓸 값이 없어 그대로 둔다.
    """
    corrected = dict(product)
    for name, spec in (extraction_truth.get("booleans") or {}).items():
        corrected[name] = spec["value"]
    return corrected


def grade_selection(truth_selected: bool, predicted: bool) -> Grade:
    """선택은 유보가 없다. 해야 하는데 안 하면 C1, 안 해도 되는데 하면 C3."""
    if truth_selected and not predicted:
        return Grade.C1
    if predicted and not truth_selected:
        return Grade.C3
    return Grade.OK


def blame_for(tool: ToolName, extraction_truth: dict, extracted: dict) -> str:
    """B에서만 생긴 C1이 누구 탓인지 나눈다(SELECTION_EVAL.md 1절 표).

    판단 필드 중 하나라도 정답이 true·null인데 추출이 false로 넘겼으면 추출 탓이다.
    그 false가 선택에게 "해당 없음"의 근거를 준 셈이다. 정답에 있는 모순을 추출이
    conflicts에서 빠뜨린 경우도 추출 탓이다(원칙 6, power_bank 전기).
    """
    booleans = extraction_truth.get("booleans") or {}
    judgement = JUDGEMENT_FIELDS.get(tool, ())
    for name in judgement:
        truth_value = booleans.get(name, {}).get("value")
        if truth_value is not False and extracted.get(name) is False:
            return Blame.EXTRACTION
    if tool is ToolName.ELECTRICAL:
        conflicts = extracted.get("conflicts") or []
        for item in extraction_truth.get("conflicts_required") or []:
            if not any(item["must_contain"] in line for line in conflicts):
                return Blame.EXTRACTION
    if any(booleans.get(name, {}).get("value") is True and extracted.get(name) is None for name in judgement):
        return Blame.SELECTION
    if any(extracted.get(name) != spec["value"] for name, spec in booleans.items()):
        return Blame.EXTRACTION_OTHER
    return Blame.NOISE


def selected_map(response: dict) -> dict[ToolName, bool]:
    """저장된 선택 결과(dict)를 툴별 선택 여부로 바꾼다."""
    parsed = ToolSelectionResponse.model_validate(response)
    return {item.tool_name: item.selected for item in parsed.decisions}


@dataclass(frozen=True)
class ToolReport:
    """툴 하나의 N회 채점 결과."""

    tool: ToolName
    truth: bool
    values: list[bool]
    grades: list[Grade]
    stability: Stability
    hard_flip: bool

    @property
    def worst(self) -> Grade:
        order = {Grade.C1: 2, Grade.C3: 1, Grade.OK: 0}
        return max(self.grades, key=lambda g: order[g])


@dataclass
class ModeReport:
    """픽스처 하나, 모드 하나의 채점 결과."""

    fixture: str
    mode: str
    runs: int
    tools: list[ToolReport] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """칸(툴) 단위 최악 등급과 회차 단위 오류 수를 함께 센다."""
        return {
            "cells": len(self.tools),
            "c1_cells": sum(1 for t in self.tools if t.worst is Grade.C1),
            "c3_cells": sum(1 for t in self.tools if t.worst is Grade.C3),
            "decisions": sum(len(t.grades) for t in self.tools),
            "c1_decisions": sum(g is Grade.C1 for t in self.tools for g in t.grades),
            "c3_decisions": sum(g is Grade.C3 for t in self.tools for g in t.grades),
            "unstable": sum(1 for t in self.tools if t.stability is Stability.UNSTABLE),
        }


def score_mode(fixture: str, mode: str, truth: dict, responses: list[dict]) -> ModeReport:
    """선택 결과 N개를 정답표와 대조한다. 실패한 회차는 넘기기 전에 뺀다."""
    if not responses:
        raise ValueError("선택 결과가 없습니다.")
    maps = [selected_map(r) for r in responses]
    report = ModeReport(fixture=fixture, mode=mode, runs=len(maps))
    for tool in ToolName:
        expected = truth["tools"][tool.value]["selected"]
        values = [m[tool] for m in maps]
        grades = [grade_selection(expected, v) for v in values]
        report.tools.append(
            ToolReport(
                tool=tool,
                truth=expected,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=is_hard_flip(values),
            )
        )
    return report


@dataclass(frozen=True)
class OnlyInB:
    """A에서는 맞았는데 B에서만 놓친 결정 하나."""

    fixture: str
    run: int
    tool: ToolName
    blame: str
    fields: dict[str, tuple[bool | None, bool | None]]


def only_in_b(
    fixture: str,
    selection_truth: dict,
    extraction_truth: dict,
    products: list[dict],
    mode_a: list[dict | None],
    mode_b: list[dict | None],
) -> list[OnlyInB]:
    """같은 추출 결과로 돌린 A·B를 회차끼리 짝지어, B에서만 생긴 C1을 찾는다.

    한쪽이라도 실패한 회차는 짝이 없어 뺀다.
    """
    found: list[OnlyInB] = []
    booleans = extraction_truth.get("booleans") or {}
    for index, (product, a, b) in enumerate(zip(products, mode_a, mode_b)):
        if a is None or b is None:
            continue
        selected_a, selected_b = selected_map(a), selected_map(b)
        for tool in ToolName:
            expected = selection_truth["tools"][tool.value]["selected"]
            if grade_selection(expected, selected_b[tool]) is not Grade.C1:
                continue
            if grade_selection(expected, selected_a[tool]) is Grade.C1:
                continue
            fields = {
                name: (booleans.get(name, {}).get("value"), product.get(name))
                for name in JUDGEMENT_FIELDS.get(tool, ())
            }
            found.append(
                OnlyInB(
                    fixture=fixture,
                    run=index,
                    tool=tool,
                    blame=blame_for(tool, extraction_truth, product),
                    fields=fields,
                )
            )
    return found

