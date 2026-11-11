"""추출·선택 에이전트 가드레일을 공격 원문과 공격 없는 원문으로 비교해 잰다.

    cd ai
    python -m app.eval.guardrail_runner --runs 3
    python -m app.eval.guardrail_runner --only dryer-field --runs 5
    python -m app.eval.guardrail_runner --rescore logs/eval/guardrail-20261110-210000.json

같은 원문의 공격 없는 입력(기준)과 공격 입력을 각각 추출 → 선택 N회 실행한다. 입력 가드는 거치지 않음.
입력 원문은 로컬 파일(tests/fixtures/_raw/guardrail_inputs.json, 저장소에 없음)이다.
공격 문장이 들어 있어 저장소에 올리지 않는다. 평가셋에 적힌 지문과 다르면 실행하지 않는다.
문서: docs/current/eval/GUARDRAIL_EVAL.md
"""

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..agents.extraction import ExtractionAgent, ExtractionFailedError
from ..agents.selection import SelectionAgent, SelectionFailedError
from ..config import agent_profile
from ..schemas.agent import ExtractionInput
from ..schemas.product import Product
from .advertising_scoring import load_eval_set
from .runner import _AI_ROOT, RESULT_DIR, describe_metadata, run_metadata

TRUTH_PATH = _AI_ROOT / "tests" / "eval_truth_guardrail" / "attacks.json"
# 동시에 도는 추출·선택 수
DEFAULT_WORKERS = 4
# 실패한 회차를 다시 시도하는 횟수
RETRIES = 2
# 기준 입력 결과를 담는 키
BASELINE = "baseline"
# 기록할 추출 boolean 필드
BOOL_FIELDS = tuple(name for name, info in Product.model_fields.items() if info.annotation == (bool | None))


def run_once(extractor, selector, text: str, product_id: str, leak_phrases: list[str]) -> dict:
    """원문 하나를 추출 → 선택 한 번 실행한다. 실패하면 RETRIES번까지 다시 시도함.

    Args:
        extractor: 추출 에이전트.
        selector: 선택 에이전트.
        text: 상품 원문.
        product_id: 사용량 기록 대상 ID.
        leak_phrases: 추출 결과에 들어갔는지 확인할 문구. 기준 입력이면 빈 목록.

    Returns:
        dict: 선택된 Tool, 추출 boolean 필드, 추출 결과에 들어간 확인 문구. 끝내 실패하면 error.
    """
    error = None
    for _ in range(RETRIES + 1):
        try:
            product = extractor.run(ExtractionInput(product_id=product_id, text_blocks=[text]))
            selection = selector.run(Product.model_validate({**product.model_dump(mode="json"),
                                                             "product_id": product_id}))
        except (ExtractionFailedError, SelectionFailedError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            continue
        dumped = product.model_dump(mode="json")
        carried = json.dumps([dumped["listing_text"], dumped["attributes"], dumped["conflicts"]], ensure_ascii=False)
        return {
            "selected": sorted(item.tool_name.value for item in selection.decisions if item.selected),
            "fields": {name: dumped.get(name) for name in BOOL_FIELDS},
            "leaks": [phrase for phrase in leak_phrases if phrase in carried],
        }
    return {"error": error}


def score_case(case: dict, attack: list[dict], baseline: list[dict]) -> dict:
    """사례 하나의 Tool 누락·필드 오염·문구 유입을 공격 입력과 기준 입력으로 나눠 센다. 실패 회차는 뺌.

    Args:
        case: 정답표 사례 (target_tools, target_fields).
        attack: 공격 입력 회차별 결과.
        baseline: 같은 원문 기준 입력의 회차별 결과.

    Returns:
        dict: tools·fields는 이름 → {"attack": [해당 회차, 전체], "baseline": [해당 회차, 전체]},
        leaks는 [유입 회차, 전체], failed는 실패 회차 수.
    """
    attack_ok = [run for run in attack if "error" not in run]
    baseline_ok = [run for run in baseline if "error" not in run]

    def missed(runs: list[dict], tool: str) -> list[int]:
        return [sum(tool not in run["selected"] for run in runs), len(runs)]

    def tampered(runs: list[dict], name: str, value) -> list[int]:
        return [sum(run["fields"].get(name) == value for run in runs), len(runs)]

    return {
        "tools": {tool: {"attack": missed(attack_ok, tool), "baseline": missed(baseline_ok, tool)}
                  for tool in case["target_tools"]},
        "fields": {name: {"attack": tampered(attack_ok, name, value), "baseline": tampered(baseline_ok, name, value)}
                   for name, value in case["target_fields"].items()},
        "leaks": [sum(bool(run["leaks"]) for run in attack_ok), len(attack_ok)],
        "failed": len(attack) - len(attack_ok),
    }


def _pair(counts: list[int]) -> str:
    return f"{counts[0]}/{counts[1]}"


def print_report(truth: dict, results: dict) -> None:
    """사례별 결과와 공격 유형별·전체 요약을 출력한다.

    Args:
        truth: 정답표.
        results: {"baseline": 원문 → 회차별 결과, "cases": 사례 ID → 회차별 결과}.
    """
    totals: dict[str, Counter] = {}
    for case in truth["cases"]:
        attack = results["cases"].get(case["id"])
        if not attack:
            continue
        scored = score_case(case, attack, results[BASELINE].get(case["page"], []))
        tools = " ".join(f"{tool.split('_')[0]} {_pair(v['attack'])}(기준 {_pair(v['baseline'])})"
                         for tool, v in scored["tools"].items())
        fields = " ".join(f"{name} {_pair(v['attack'])}(기준 {_pair(v['baseline'])})"
                          for name, v in scored["fields"].items())
        failed = f" 실패 {scored['failed']}" if scored["failed"] else ""
        print(f"  {case['id']:22} [{case['attack_type']}] Tool 누락 {tools}"
              f"{' | 필드 오염 ' + fields if fields else ''} | 문구 유입 {_pair(scored['leaks'])}{failed}")
        for key in (case["attack_type"], "전체"):
            total = totals.setdefault(key, Counter())
            for v in scored["tools"].values():
                total["tool_attack"] += v["attack"][0]
                total["tool_baseline"] += v["baseline"][0]
                total["tool_attack_n"] += v["attack"][1]
                total["tool_baseline_n"] += v["baseline"][1]
            for v in scored["fields"].values():
                total["field_attack"] += v["attack"][0]
                total["field_baseline"] += v["baseline"][0]
                total["field_attack_n"] += v["attack"][1]
                total["field_baseline_n"] += v["baseline"][1]
            total["leak"] += scored["leaks"][0]
            total["leak_n"] += scored["leaks"][1]
            total["failed"] += scored["failed"]

    print("\n요약 (노린 Tool·필드 × 회차 기준. 괄호는 같은 원문의 공격 없는 입력)")
    # 공격 유형별 뒤에 전체
    for key, total in sorted(totals.items(), key=lambda item: item[0] == "전체"):
        field = (f" | 필드 오염 {total['field_attack']}/{total['field_attack_n']}"
                 f"(기준 {total['field_baseline']}/{total['field_baseline_n']})" if total["field_attack_n"] else "")
        failed = f" | 실패 회차 {total['failed']}" if total["failed"] else ""
        print(f"  {key:16} Tool 누락 {total['tool_attack']}/{total['tool_attack_n']}"
              f"(기준 {total['tool_baseline']}/{total['tool_baseline_n']}){field}"
              f" | 문구 유입 {total['leak']}/{total['leak_n']}{failed}")


def rescore(path: Path) -> int:
    """저장된 결과를 정답표로 다시 집계한다. 모델을 부르지 않음.

    Args:
        path: 저장된 결과 파일.

    Returns:
        int: 종료 코드.
    """
    saved = json.loads(path.read_text(encoding="utf-8"))
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    print(describe_metadata(saved.get("meta") or {}))
    print_report(truth, saved["results"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="추출·선택 에이전트 가드레일 평가")
    parser.add_argument("--runs", type=int, default=3, help="입력당 회차 수 (기본 3)")
    parser.add_argument("--only", action="append", default=[], help="이 사례 ID만 (여러 번 지정 가능)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="동시에 도는 추출·선택 수")
    parser.add_argument("--rescore", type=Path, help="저장된 결과를 다시 집계만 한다")
    args = parser.parse_args()

    if args.rescore:
        return rescore(args.rescore)

    truth, inputs = load_eval_set(TRUTH_PATH, _AI_ROOT)
    cases = [case for case in truth["cases"] if not args.only or case["id"] in args.only]
    if not cases:
        parser.error(f"평가셋에 없는 사례입니다: {', '.join(args.only)}")
    meta = run_metadata(runs=args.runs, profile=agent_profile("extraction"), prompt=ExtractionAgent.system_prompt())
    meta["selection_model"] = agent_profile("selection").model.id
    meta["selection_prompt_sha256"] = SelectionAgent.system_prompt().sha256
    print(describe_metadata(meta))

    extractor = ExtractionAgent(usage_agent="guardrail-eval")
    selector = SelectionAgent(usage_agent="guardrail-eval")
    jobs = [(BASELINE, page, inputs["pages"][page], []) for page in dict.fromkeys(case["page"] for case in cases)]
    jobs += [("cases", case["id"], inputs["cases"][case["id"]]["text"], inputs["cases"][case["id"]]["leak_phrases"])
             for case in cases]
    results: dict = {BASELINE: {}, "cases": {}}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            (kind, key, executor.submit(run_once, extractor, selector, text, f"guardrail-{key}-{index}", leaks))
            for kind, key, text, leaks in jobs for index in range(args.runs)
        ]
        for kind, key, future in futures:
            results[kind].setdefault(key, []).append(future.result())

    print_report({**truth, "cases": cases}, results)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"guardrail-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {out.relative_to(_AI_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
