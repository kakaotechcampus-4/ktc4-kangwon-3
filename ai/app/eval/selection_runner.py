"""저장된 추출 결과로 선택 에이전트를 돌려 선택 정답표와 대조한다.

    python -m app.eval.selection_runner --extraction-log logs/eval/20261006-235404.json
    python -m app.eval.selection_runner --extraction-log A.json --extraction-log B.json --runs 10
    python -m app.eval.selection_runner --rescore logs/eval/selection-20261007-120000.json

추출을 다시 부르지 않는다. 추출 평가가 남긴 결과 파일을 입력으로 쓰므로 선택 호출 비용만 든다.
추출 결과 하나마다 두 번 선택한다(SELECTION_EVAL.md 1절).

- 모드 B: 추출 결과 그대로. 실제 파이프라인과 같다.
- 모드 A: 같은 추출 결과에서 boolean만 정답값으로 바꾼 입력. 선택 에이전트 자체의 오류를 본다.

입력이 boolean만 다르므로, A에서는 맞았는데 B에서만 놓친 툴이 추출 오류가 선택에 미친 영향이다.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from ..agents.selection import _PROMPT_PATH as SELECTION_PROMPT_PATH
from ..agents.selection import SelectionAgent, SelectionFailedError
from ..config import load_settings
from ..schemas.product import Product
from .grading import Grade, Stability
from .runner import RESULT_DIR, TRUTH_DIR, describe_metadata, prompt_fingerprint, run_metadata
from .scoring import load_truth as load_extraction_truth
from .selection_scoring import (
    Blame,
    ModeReport,
    OnlyInB,
    correct_booleans,
    load_selection_truth,
    only_in_b,
    score_mode,
)

SELECTION_TRUTH_DIR = TRUTH_DIR.parent / "eval_truth_selection"
MODES = ("A", "B")


def load_extraction_outputs(paths: list[Path]) -> tuple[dict[str, list[dict]], str, str]:
    """추출 결과 파일들을 픽스처별로 합친다. 실패한 회차는 뺀다.

    프롬프트나 모델이 다른 기록을 섞으면 어떤 추출로 잰 선택 결과인지 알 수 없으므로 막는다.
    프롬프트 지문이 같아도 모델이 다르면(gpt-4.1-mini와 Luna, #279) 출력이 다르다.

    Returns:
        픽스처별 추출 결과, 추출 프롬프트 지문, 추출 모델.
    """
    merged: dict[str, list[dict]] = {}
    conditions: list[tuple[str, str]] = []
    for path in paths:
        saved = json.loads(path.read_text(encoding="utf-8"))
        meta = saved.get("meta") or {}
        conditions.append((meta.get("prompt_sha256") or "알 수 없음", meta.get("model") or "알 수 없음"))
        for name, outputs in saved["results"].items():
            merged.setdefault(name, []).extend(o for o in outputs if not o.get("_failed"))
    if len({prompt for prompt, _ in conditions}) > 1:
        raise ValueError(f"추출 프롬프트가 다른 기록을 섞었습니다: {sorted({p for p, _ in conditions})}")
    if len({model for _, model in conditions}) > 1:
        raise ValueError(f"추출 모델이 다른 기록을 섞었습니다: {sorted({m for _, m in conditions})}")
    return merged, conditions[0][0], conditions[0][1]


def _select(agent: SelectionAgent, product: dict, product_id: str) -> dict | None:
    """선택 한 번. 실패한 회차는 None으로 남긴다(사용량은 에이전트가 직접 기록한다)."""
    try:
        response = agent.select(Product.model_validate({**product, "product_id": product_id}))
    except SelectionFailedError as exc:
        print(f"      선택 실패: {exc}", file=sys.stderr)
        return None
    return response.model_dump(mode="json")


def run_fixture(agent: SelectionAgent, name: str, products: list[dict], extraction_truth: dict) -> dict:
    """추출 결과마다 모드 A·B로 한 번씩 선택한다. 회차끼리 짝지을 수 있게 순서를 지킨다."""
    result: dict = {"products": products, "A": [], "B": []}
    for index, product in enumerate(products):
        started = time.perf_counter()
        result["B"].append(_select(agent, product, f"selection-eval-{name}-{index}-B"))
        result["A"].append(
            _select(agent, correct_booleans(product, extraction_truth), f"selection-eval-{name}-{index}-A")
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        print(f"    {index + 1}/{len(products)} 완료 ({elapsed}ms)", file=sys.stderr)
    return result


def score_fixture(name: str, data: dict) -> tuple[dict[str, ModeReport], list[OnlyInB]]:
    selection_truth = load_selection_truth(SELECTION_TRUTH_DIR / f"{name}.json")
    extraction_truth = load_extraction_truth(TRUTH_DIR / f"{name}.json")
    reports = {
        mode: score_mode(name, mode, selection_truth, [r for r in data[mode] if r is not None])
        for mode in MODES
        if any(r is not None for r in data[mode])
    }
    diffs = only_in_b(name, selection_truth, extraction_truth, data["products"], data["A"], data["B"])
    return reports, diffs


def print_fixture(name: str, reports: dict[str, ModeReport], diffs: list[OnlyInB]) -> None:
    parts = []
    for mode in MODES:
        if mode not in reports:
            parts.append(f"{mode}: 전 회차 실패")
            continue
        c = reports[mode].counts()
        parts.append(f"{mode}: C1 {c['c1_decisions']} C3 {c['c3_decisions']} (결정 {c['decisions']}개)")
    print(f"\n### {name}  " + " | ".join(parts))
    for tool_reports in zip(*(reports[m].tools for m in MODES if m in reports)):
        if all(t.worst is Grade.OK and t.stability is not Stability.UNSTABLE for t in tool_reports):
            continue
        values = "  ".join(
            f"{m}={''.join('O' if v else '.' for v in t.values)}[{t.worst.value}]"
            for m, t in zip([m for m in MODES if m in reports], tool_reports)
        )
        print(f"  {tool_reports[0].tool.value:32s} 정답={'선택' if tool_reports[0].truth else '미선택'}  {values}")
    for diff in diffs:
        fields = ", ".join(f"{k} 정답={t!r}/추출={e!r}" for k, (t, e) in diff.fields.items())
        label = "정답과 다른 boolean: " if diff.blame == Blame.EXTRACTION_OTHER else ""
        print(f"  B에서만 놓침 {diff.run + 1}회차 {diff.tool.value} → {diff.blame} 탓  ({label}{fields or '판단 필드 없음'})")


def print_summary(all_reports: list[dict[str, ModeReport]], all_diffs: list[OnlyInB]) -> None:
    print("\n## 전체")
    for mode in MODES:
        counts = Counter()
        for reports in all_reports:
            if mode in reports:
                counts.update(reports[mode].counts())
        if not counts["decisions"]:
            continue
        print(
            f"  모드 {mode}: C1 {counts['c1_decisions']}/{counts['decisions']} "
            f"({counts['c1_decisions'] / counts['decisions']:.1%})  "
            f"C3 {counts['c3_decisions']}/{counts['decisions']} "
            f"({counts['c3_decisions'] / counts['decisions']:.1%})  "
            f"C1 칸 {counts['c1_cells']}/{counts['cells']}  불안정 칸 {counts['unstable']}"
        )
    blame = Counter(d.blame for d in all_diffs)
    print(f"  B에서만 놓친 결정 {len(all_diffs)}개: " + ", ".join(f"{k} 탓 {v}" for k, v in blame.items()))


def report_all(results: dict[str, dict]) -> None:
    all_reports, all_diffs = [], []
    for name, data in results.items():
        reports, diffs = score_fixture(name, data)
        print_fixture(name, reports, diffs)
        all_reports.append(reports)
        all_diffs.extend(diffs)
    print_summary(all_reports, all_diffs)


def warn_if_prompt_changed(meta: dict | None) -> list[str]:
    """저장된 결과가 지금 선택 프롬프트로 나온 값인지 확인한다."""
    saved = (meta or {}).get("prompt_sha256")
    if not saved:
        return ["[주의] 기록에 선택 프롬프트 지문이 없습니다. 같은 프롬프트로 잰 값인지 알 수 없습니다."]
    current = prompt_fingerprint(SELECTION_PROMPT_PATH)
    if saved != current:
        return [
            f"[주의] 지금과 다른 선택 프롬프트로 나온 결과입니다 "
            f"(기록 {saved[:12]} / 현재 {current[:12]}). 같은 기준선으로 비교하면 안 됩니다."
        ]
    return []


def rescore(path: Path) -> int:
    """저장된 선택 결과를 LLM 재호출 없이 다시 채점한다."""
    saved = json.loads(path.read_text(encoding="utf-8"))
    meta = saved.get("meta")
    for line in warn_if_prompt_changed(meta):
        print(line, file=sys.stderr)
    if meta:
        print(f"측정 조건: {describe_metadata(meta)}", file=sys.stderr)
    report_all(saved["results"])
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="선택 에이전트 평가")
    parser.add_argument("--extraction-log", type=Path, action="append", default=[],
                        help="입력으로 쓸 추출 평가 결과 파일 (여러 번 지정하면 합친다)")
    parser.add_argument("--fixture", action="append", default=[], help="선택 정답표 이름(확장자 제외)")
    parser.add_argument("--runs", type=int, default=5, help="픽스처당 쓸 추출 결과 수 (기본 5)")
    parser.add_argument("--rescore", type=Path, help="저장된 선택 결과를 재채점만 한다")
    args = parser.parse_args()

    if args.rescore:
        return rescore(args.rescore)
    if not args.extraction_log:
        parser.error("--extraction-log 또는 --rescore 를 지정하세요.")

    outputs, extraction_prompt, extraction_model = load_extraction_outputs(args.extraction_log)
    with_truth = [p.stem for p in sorted(SELECTION_TRUTH_DIR.glob("*.json"))]
    names = args.fixture or [n for n in with_truth if n in outputs]
    # 모델을 만들기 전에 입력이 다 있는지 본다. 뒤쪽이 비면 앞쪽 호출이 통째로 낭비된다.
    missing = [n for n in names if n not in with_truth or not outputs.get(n)]
    if missing:
        print(f"선택 정답표나 추출 결과가 없는 픽스처입니다: {', '.join(missing)}", file=sys.stderr)
        return 1

    # 평가로 쓴 비용이 운영 비용과 섞이면 어느 쪽이 얼마인지 볼 수 없다.
    agent = SelectionAgent(usage_agent="selection-eval")
    meta = run_metadata(runs=args.runs, model=load_settings().model, prompt_path=SELECTION_PROMPT_PATH)
    # 어떤 추출 결과로 잰 선택인지 함께 남긴다. 추출이 바뀌면 모드 B 수치가 달라진다.
    meta["extraction_logs"] = [p.as_posix() for p in args.extraction_log]
    meta["extraction_prompt_sha256"] = extraction_prompt
    meta["extraction_model"] = extraction_model
    print(f"측정 조건: {describe_metadata(meta)} / 추출 프롬프트 {extraction_prompt[:12]} / 추출 모델 {extraction_model}", file=sys.stderr)
    if meta["git_dirty"]:
        print("  커밋하지 않은 수정이 있습니다. 기록된 커밋만으로는 재현되지 않습니다.", file=sys.stderr)

    results: dict[str, dict] = {}
    for name in names:
        products = outputs[name][: args.runs]
        print(f"  {name} x{len(products)} (모드 A·B)", file=sys.stderr)
        results[name] = run_fixture(agent, name, products, load_extraction_truth(TRUTH_DIR / f"{name}.json"))

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"selection-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    report_all(results)
    print(f"\n실행 결과 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
