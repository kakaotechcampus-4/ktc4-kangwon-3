"""사용자 시나리오 끝단 평가 채점. 실제 상품 원문 → 추출 → 선택 결과를 선택 정답과 대조한다. LLM을 부르지 않는다.

"걸리는 규제를 빠짐없이 골랐나"를 상품 단위로 센다(문서: docs/current/eval/SCENARIO_EVAL.md).
- 빠뜨림(C1): 정답 selected=true인데 안 고름. 규제가 조용히 누락되므로 무겁다.
- 과잉(C3): 정답 false인데 고름. 비용·지연만 늘어 가볍게 본다.
- 무누락: 그 상품의 모든 회차에서 빠뜨림이 0. "가끔 놓친다"를 숨기지 않으려고 회차 하나라도 놓치면 실패다.
- 실패한 회차(추출·선택 예외)는 사용자에게 진단서가 안 나가므로 정답 Tool을 전부 빠뜨린 것으로 센다.
"""

from collections import Counter

from ..schemas.schemas import ToolName
from .selection_scoring import JUDGEMENT_FIELDS, selected_map

CAUSE_EXTRACTION_FALSE = "추출이 false로 넘김"
CAUSE_SELECTION_NULL = "선택이 null을 없음으로 봄"
CAUSE_SELECTION_MISSED = "선택이 근거를 보고도 놓침"
CAUSE_NO_JUDGEMENT_FIELD = "판단 칸 없는 Tool"
CAUSE_FAILED = "실행 실패"
CAUSE_UNCLASSIFIED = "분류 안 함"
# 정답의 근거가 상세 이미지·알리 설명 글에만 있어 평가 입력(text.txt)으로는 알 수 없던 빠뜨림
CAUSE_NOT_IN_INPUT = "글 입력에 근거 없음"
CAUSES = (
    CAUSE_EXTRACTION_FALSE, CAUSE_SELECTION_NULL, CAUSE_SELECTION_MISSED,
    CAUSE_NO_JUDGEMENT_FIELD, CAUSE_NOT_IN_INPUT, CAUSE_FAILED, CAUSE_UNCLASSIFIED,
)


def _expected(truth: dict) -> dict[ToolName, bool]:
    return {ToolName(name): spec["selected"] for name, spec in truth["tools"].items()}


def missed_tools(truth: dict, response: dict | None) -> list[ToolName]:
    """정답에서 골라야 하는데 안 고른 Tool. 실패한 회차(None)면 골라야 할 Tool 전부."""
    expected = _expected(truth)
    chosen = selected_map(response) if response is not None else {}
    return [tool for tool in ToolName if expected[tool] and not chosen.get(tool, False)]


def over_selected_tools(truth: dict, response: dict | None) -> list[ToolName]:
    """정답에서 안 골라도 되는데 고른 Tool. 실패한 회차는 고른 게 없다."""
    if response is None:
        return []
    expected = _expected(truth)
    chosen = selected_map(response)
    return [tool for tool in ToolName if not expected[tool] and chosen.get(tool, False)]


def classify_miss(tool: ToolName, extracted: dict | None, extraction_truth: dict | None) -> str:
    """빠뜨린 Tool 하나의 원인을 그 Tool의 판단 칸으로 나눈다(SELECTION_EVAL.md 1절을 모드 B만으로 줄인 것)."""
    if extracted is None:
        return CAUSE_FAILED
    if extraction_truth is None:
        return CAUSE_UNCLASSIFIED
    fields = JUDGEMENT_FIELDS.get(tool, ())
    if not fields:
        return CAUSE_NO_JUDGEMENT_FIELD
    truth_values = {name: spec.get("value") for name, spec in (extraction_truth.get("booleans") or {}).items()}
    if any(extracted.get(f) is False and truth_values.get(f) is not False for f in fields):
        return CAUSE_EXTRACTION_FALSE
    if any(extracted.get(f) is None and truth_values.get(f) is True for f in fields):
        return CAUSE_SELECTION_NULL
    return CAUSE_SELECTION_MISSED


def summarize(products: dict[str, dict], truths: dict[str, dict], extraction_truths: dict[str, dict | None]) -> dict:
    """상품별 회차 결과를 모아 보고서 숫자를 만든다.

    Args:
        products: 상품 이름 → {"runs": [{"extracted": dict | None, "selection": dict | None}], "retries": int,
            "input_fallback": bool}. 실패한 회차는 selection이 None이다.
        truths: 상품 이름 → 선택 정답.
        extraction_truths: 상품 이름 → 추출 정답(없으면 None, 원인을 분류하지 않음).

    Returns:
        dict: products, pass_all_runs, pass_rate_all_runs, pass_rate_per_run, c1_by_tool, c3_by_tool, causes,
            image_only_misses, failed_runs, retries, input_fallbacks, misses.
    """
    c1 = Counter({tool.value: 0 for tool in ToolName})
    c3 = Counter({tool.value: 0 for tool in ToolName})
    causes = Counter({cause: 0 for cause in CAUSES})
    misses: list[dict] = []
    pass_all = runs_total = runs_passed = failed = image_only = retries = fallbacks = 0
    # Tool 하나를 빼고 셌을 때의 무누락 상품 수 (예: 표시광고 빼고). 발표용 숫자를 재채점으로 재현하려고 둔다.
    pass_excluding = Counter({tool.value: 0 for tool in ToolName})
    for name, product in products.items():
        truth = truths[name]
        image_only_tools = {ToolName(t) for t, spec in truth["tools"].items() if spec.get("image_only")}
        retries += product.get("retries", 0)
        fallbacks += bool(product.get("input_fallback"))
        product_clean = True
        missed_per_run: list[list[ToolName]] = []
        for index, run in enumerate(product["runs"]):
            selection = run["selection"]
            runs_total += 1
            failed += selection is None
            missed = missed_tools(truth, selection)
            missed_per_run.append(missed)
            for tool in over_selected_tools(truth, selection):
                c3[tool.value] += 1
            for tool in missed:
                c1[tool.value] += 1
                not_in_input = tool in image_only_tools
                image_only += not_in_input
                if selection is None:
                    cause = CAUSE_FAILED
                elif not_in_input:
                    cause = CAUSE_NOT_IN_INPUT
                else:
                    cause = classify_miss(tool, run["extracted"], extraction_truths.get(name))
                causes[cause] += 1
                misses.append({"product": name, "run": index, "tool": tool.value, "cause": cause, "image_only": not_in_input})
            if missed:
                product_clean = False
            else:
                runs_passed += 1
        pass_all += product_clean
        for excluded in ToolName:
            pass_excluding[excluded.value] += all(not [t for t in m if t is not excluded] for m in missed_per_run)
    count = len(products)
    return {
        "products": count,
        "pass_all_runs": pass_all,
        "pass_rate_all_runs": pass_all / count if count else 0.0,
        "pass_rate_per_run": runs_passed / runs_total if runs_total else 0.0,
        "pass_all_runs_excluding": dict(pass_excluding),
        "c1_by_tool": dict(c1),
        "c3_by_tool": dict(c3),
        "causes": dict(causes),
        "image_only_misses": image_only,
        "failed_runs": failed,
        "retries": retries,
        "input_fallbacks": fallbacks,
        "misses": misses,
    }


_TOOL_LABELS = {
    "customs_requirements": "통관", "radio_compliance": "전파", "food_drug_safety": "식품·의약",
    "electrical_safety": "전기", "children_product_safety": "어린이", "labeling_advertising_detection": "표시광고",
}


def render_report(summary: dict, meta: dict, title: str) -> str:
    """측정 하나의 결과를 마크다운 절로 만든다. 사례 문장은 사람이 채운다."""
    s = summary
    lines = [
        f"## {title}",
        "",
        f"측정 조건: 모델 {meta.get('model', '알 수 없음')} / 커밋 {meta.get('git_commit', '알 수 없음')} / "
        f"추출 프롬프트 {str(meta.get('prompt_sha256', ''))[:12]} / 선택 프롬프트 {str(meta.get('selection_prompt_sha256', ''))[:12]}",
        "",
        "| 숫자 | 값 |",
        "|---|---|",
        f"| 무누락 상품 (모든 회차에서 빠뜨림 0) | {s['pass_all_runs']}/{s['products']} ({s['pass_rate_all_runs']:.0%}) |",
        f"| 회차 평균 무누락률 | {s['pass_rate_per_run']:.0%} |",
        f"| 무누락 상품 (표시광고 빼고) | {s['pass_all_runs_excluding']['labeling_advertising_detection']}/{s['products']} |",
        f"| 실패 회차 / 재시도 | {s['failed_runs']} / {s['retries']} |",
        f"| 글 입력에 근거가 없어(이미지·설명 글에만) 놓친 Tool | {s['image_only_misses']} |",
        f"| 펼치기 전 글이 없어 펼친 글로 대체한 상품 | {s['input_fallbacks']} |",
        "",
        "| Tool | 빠뜨림 | 과잉 선택 |",
        "|---|---|---|",
        *[f"| {_TOOL_LABELS.get(t, t)} | {s['c1_by_tool'][t]} | {s['c3_by_tool'][t]} |" for t in s["c1_by_tool"]],
        "",
        "| 빠뜨림 원인 | 수 |",
        "|---|---|",
        *[f"| {cause} | {n} |" for cause, n in s["causes"].items() if n],
        "",
        "### 빠뜨림 사례",
        "",
        "(사람이 채움)",
        "",
    ]
    return "\n".join(lines)
