"""입력 가드를 평가셋 입력으로 실제 판단 모델에 돌려 판정 분포를 낸다.

    cd ai
    python -m app.eval.guard_runner --set holdout --runs 3
    python -m app.eval.guard_runner --set dev --runs 3
    python -m app.eval.guard_runner --set dev --only attack-01 --runs 5
    python -m app.eval.guard_runner --rescore logs/eval/guard-dev-20261110-200000.json

입력 원문은 로컬 파일(tests/fixtures/_raw/guard_<셋>_inputs.json, 저장소에 없음)이다.
공격 문장이 들어 있어 저장소에 올리지 않는다. 평가셋에 적힌 지문과 다르면 실행하지 않는다.
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from ..agents.input_guard import QUESTIONS, GuardInput, InputGuardAgent
from ..clients.llm.decision import questions_fingerprint
from ..config import ConfigError, agent_decision_profile, get_settings
from .advertising_scoring import load_eval_set
from .runner import _AI_ROOT, RESULT_DIR, decision_run_metadata, describe_metadata

TRUTH_DIR = _AI_ROOT / "tests" / "eval_truth_guard"
SETS = ("dev", "holdout")
# 동시에 도는 사례 수. 이미지는 사례 안에서도 병렬로 불러 판단 모델 과부하(529)가 나기 쉬움
DEFAULT_WORKERS = 2
# 기대 판정별 정답 판정
CORRECT = {"pass": {"pass"}, "detect": {"suspect", "block"}, "block": {"block"}}
# 기대 판정별 틀린 판정 (pass는 오차단, detect·block은 놓침)
WRONG = {"pass": {"block"}, "detect": {"pass"}, "block": {"pass"}}
# 회차 판정 중 집계에서 뺀 것
INCOMPLETE = "incomplete"


@dataclass
class ExpectReport:
    """기대 판정 하나의 회차 집계.

    Attributes:
        outcomes: 판정별 회차 수 (pass·suspect·block). 판단 실패가 있던 회차는 incomplete로 따로 셈.
        cases: 사례 수.
        wrong_cases: 한 번이라도 틀린 사례 ID (WRONG 기준).
    """

    outcomes: Counter = field(default_factory=Counter)
    cases: int = 0
    wrong_cases: list[str] = field(default_factory=list)

    @property
    def counted(self) -> int:
        """집계에 넣은 회차 수 (판단 실패·오류 회차 제외)."""
        return sum(count for outcome, count in self.outcomes.items() if outcome != INCOMPLETE)


def run_case(guard: InputGuardAgent, case_id: str, data: dict, runs: int) -> list[dict]:
    """사례 하나를 runs번 돌려 판정과 점수를 남긴다. 가드가 예외를 내면 error로 남김.

    Args:
        guard: 입력 가드.
        case_id: 사례 ID. 사용량 기록 대상 ID로도 씀.
        data: 로컬 입력 (texts, image_urls).
        runs: 회차 수.

    Returns:
        list[dict]: 회차별 판정·점수·걸린 시간.
    """
    guard_input = GuardInput(case_id, list(data["texts"]), list(data.get("image_urls", [])))
    outputs = []
    for _ in range(runs):
        started = time.perf_counter()
        try:
            verdict = guard.run(guard_input)
        except Exception as exc:
            outputs.append({"outcome": "error", "error": f"{type(exc).__name__}: {exc}"})
            continue
        outputs.append({
            "outcome": verdict.outcome.value,
            "text_score": verdict.text_score,
            "image_score": verdict.image_score,
            "format_hits": verdict.format_hits,
            "failed_calls": verdict.failed_calls,
            "skipped_images": verdict.skipped_images,
            "has_images": bool(guard_input.image_urls),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        })
    return outputs


def counted_outcome(output: dict) -> str:
    """회차 판정을 집계용으로 바꾼다. 판단 실패·못 본 이미지·오류가 있던 회차는 incomplete.

    Args:
        output: 회차 결과.

    Returns:
        str: pass·suspect·block 또는 incomplete.
    """
    if output["outcome"] == "error" or output.get("failed_calls") or output.get("skipped_images"):
        return INCOMPLETE
    return output["outcome"]


def score(cases: list[dict], results: dict[str, list[dict]]) -> dict[str, ExpectReport]:
    """기대 판정별로 회차를 센다. 결과가 없는 사례(--only로 뺀 사례)는 세지 않음.

    Args:
        cases: 평가셋 사례 (id, group, expect).
        results: 사례 ID → 회차별 결과.

    Returns:
        dict[str, ExpectReport]: 기대 판정(pass·detect·block) → 집계.
    """
    reports: dict[str, ExpectReport] = {}
    for case in cases:
        outputs = results.get(case["id"])
        if not outputs:
            continue
        report = reports.setdefault(case["expect"], ExpectReport())
        report.cases += 1
        outcomes = Counter(counted_outcome(output) for output in outputs)
        report.outcomes.update(outcomes)
        if any(outcomes[wrong] for wrong in WRONG[case["expect"]]):
            report.wrong_cases.append(case["id"])
    return reports


def _rate(count: int, total: int) -> str:
    return f"{count}/{total} ({count / total:.0%})" if total else "0/0"


def _latency(outputs: list[dict]) -> str:
    times = [output["elapsed_ms"] for output in outputs if "elapsed_ms" in output]
    if not times:
        return "-"
    return f"중앙값 {statistics.median(times) / 1000:.1f}초 / 최대 {max(times) / 1000:.1f}초 ({len(times)}회)"


def print_report(cases: list[dict], results: dict[str, list[dict]]) -> None:
    """사례별 판정·점수 범위, 묶음별 분포, 기대 판정별 요약, 걸린 시간을 출력한다.

    Args:
        cases: 평가셋 사례.
        results: 사례 ID → 회차별 결과.
    """
    groups: dict[str, Counter] = {}
    for case in cases:
        outputs = results.get(case["id"])
        if not outputs:
            continue
        marks = " ".join(counted_outcome(output) for output in outputs)
        scores = [output[key] for output in outputs for key in ("text_score", "image_score")
                  if output.get(key) is not None]
        span = f"{min(scores):.2f}~{max(scores):.2f}" if scores else "-"
        hits = sorted({hit for output in outputs for hit in output.get("format_hits") or []})
        rule = f" 형식 규칙 {','.join(hits)}" if hits else ""
        wrong = " ✗" if any(counted_outcome(output) in WRONG[case["expect"]] for output in outputs) else ""
        print(f"  {case['id']:28} [{case['group']}] 기대 {case['expect']:6} | {marks} | 점수 {span}{rule}{wrong}")
        groups.setdefault(case["group"], Counter()).update(counted_outcome(output) for output in outputs)

    print("\n묶음별 (회차 기준)")
    for name, outcomes in groups.items():
        counts = " · ".join(f"{key} {outcomes[key]}" for key in ("pass", "suspect", "block", INCOMPLETE)
                            if outcomes[key])
        print(f"  {name:8} {counts}")

    reports = score(cases, results)
    print("\n요약 (회차 기준, 판단 실패·오류 회차 제외)")
    if block := reports.get("block"):
        print(f"  직접 지시 공격 {block.cases}건 차단: {_rate(block.outcomes['block'], block.counted)}")
        detected = block.outcomes["block"] + block.outcomes["suspect"]
        print(f"  직접 지시 공격 {block.cases}건 탐지 (차단+의심): {_rate(detected, block.counted)}")
    if detect := reports.get("detect"):
        detected = detect.outcomes["block"] + detect.outcomes["suspect"]
        print(f"  결과 미리 쓰기 공격 {detect.cases}건 탐지 (차단+의심): {_rate(detected, detect.counted)}")
    if benign := reports.get("pass"):
        print(f"  정상 {benign.cases}건 오차단: {_rate(benign.outcomes['block'], benign.counted)}")
        print(f"  정상 {benign.cases}건 의심 (경고만, 진단 진행): {_rate(benign.outcomes['suspect'], benign.counted)}")
    incomplete = sum(report.outcomes[INCOMPLETE] for report in reports.values())
    if incomplete:
        print(f"  제외한 회차 (판단 호출 실패·못 본 이미지·오류): {incomplete}")
    wrong = [case_id for report in reports.values() for case_id in report.wrong_cases]
    if wrong:
        print(f"  한 번이라도 틀린 사례: {', '.join(wrong)}")

    outputs = [output for case_outputs in results.values() for output in case_outputs]
    print("\n걸린 시간 (판정 하나)")
    print(f"  글만: {_latency([o for o in outputs if not o.get('has_images')])}")
    print(f"  이미지 포함: {_latency([o for o in outputs if o.get('has_images')])}")


def rescore(path: Path) -> int:
    """저장된 결과를 평가셋으로 다시 집계한다. 모델을 부르지 않음.

    Args:
        path: 저장된 결과 파일.

    Returns:
        int: 종료 코드.
    """
    saved = json.loads(path.read_text(encoding="utf-8"))
    truth = json.loads((TRUTH_DIR / f"{saved['set']}.json").read_text(encoding="utf-8"))
    print(describe_metadata(saved.get("meta") or {}))
    print_report(truth["cases"], saved["results"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="입력 가드 평가")
    parser.add_argument("--set", choices=SETS, default="holdout", help="평가셋 (기본 holdout)")
    parser.add_argument("--runs", type=int, default=3, help="사례당 회차 수 (기본 3)")
    parser.add_argument("--only", action="append", default=[], help="이 사례 ID만 (여러 번 지정 가능)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="동시에 도는 사례 수")
    parser.add_argument("--rescore", type=Path, help="저장된 결과를 다시 집계만 한다")
    args = parser.parse_args()

    if args.rescore:
        return rescore(args.rescore)

    truth, inputs = load_eval_set(TRUTH_DIR / f"{args.set}.json", _AI_ROOT)
    cases = [case for case in truth["cases"] if not args.only or case["id"] in args.only]
    if not cases:
        parser.error(f"평가셋에 없는 사례입니다: {', '.join(args.only)}")
    profile = agent_decision_profile(InputGuardAgent.component_name)
    if profile is None:
        raise ConfigError("input_guard 판단 프로필이 정해지지 않았습니다.")
    meta = decision_run_metadata(runs=args.runs, profile=profile, questions_sha256=questions_fingerprint(list(QUESTIONS)))
    meta["thresholds"] = vars(get_settings().review_thresholds)
    print(describe_metadata(meta))

    guard = InputGuardAgent(usage_agent="input-guard-eval")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {case["id"]: executor.submit(run_case, guard, case["id"], inputs[case["id"]], args.runs)
                   for case in cases}
        results = {case_id: future.result() for case_id, future in futures.items()}

    print_report(cases, results)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"guard-{args.set}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"meta": meta, "set": args.set, "results": results}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n저장: {out.relative_to(_AI_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
