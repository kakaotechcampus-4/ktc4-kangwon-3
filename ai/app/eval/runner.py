"""픽스처를 N회 추출해 정답표와 대조한다.

    python -m app.eval.runner --all --runs 5
    python -m app.eval.runner --fixture power_bank --runs 3
    python -m app.eval.runner --rescore runs/2026-09-16.json   (재호출 없이 다시 채점)

실행 결과 원본을 항상 파일로 남긴다. 채점 기준을 고치면 LLM을 다시 부르지 않고
같은 데이터로 재채점할 수 있어야 기준을 마음 놓고 다듬을 수 있다.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from ..agents.extraction import ExtractionAgent, ExtractionFailedError
from ..config import DEFAULT_MODEL
from ..schemas.agent import ExtractionInput
from ..usage import record
from .grading import Grade, Stability
from .scoring import FixtureReport, load_truth, score

_AI_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = _AI_ROOT / "tests" / "fixtures" / "_raw"
TRUTH_DIR = _AI_ROOT / "tests" / "eval_truth"
RESULT_DIR = _AI_ROOT / "logs" / "eval"


class RawFixtureMissing(FileNotFoundError):
    """원문 픽스처가 로컬에 없다. 저장소에는 축약본만 커밋된다."""


def run_fixture(agent: ExtractionAgent, name: str, runs: int) -> list[dict]:
    """픽스처 하나를 N회 추출한다. 실패한 회차도 결과로 남긴다."""
    path = RAW_DIR / name
    if not path.exists():
        # 상용 상세페이지 원문은 저장소가 public이라 커밋하지 않는다
        # (tests/fixtures/README.md). 평가를 돌리려면 원문을 따로 받아야 한다.
        raise RawFixtureMissing(
            f"원문 픽스처가 없습니다: {path}. "
            f"저장소에는 축약본만 들어 있습니다. 원문은 팀에서 따로 공유받아 "
            f"{RAW_DIR} 에 넣어주세요 (tests/fixtures/README.md 참고)."
        )
    text = path.read_text(encoding="utf-8")
    outputs: list[dict] = []
    for index in range(runs):
        source = ExtractionInput(product_id=f"eval-{Path(name).stem}-{index}", text_blocks=[text])
        started = time.perf_counter()
        try:
            product = agent.extract(source)
        except ExtractionFailedError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            # 실패도 한 회차로 센다. "5회 중 1회 실패"를 집계할 수 있어야 한다.
            record("extraction-eval", None, configured_model=DEFAULT_MODEL,
                   subject_id=source.product_id, ok=False, elapsed_ms=elapsed,
                   error_type=type(exc.__cause__ or exc).__name__)
            outputs.append({"_failed": True, "_error": str(exc)})
            print(f"    {index + 1}/{runs} 실패: {exc}", file=sys.stderr)
            continue
        elapsed = int((time.perf_counter() - started) * 1000)
        record("extraction-eval", None, configured_model=DEFAULT_MODEL,
               subject_id=source.product_id, ok=True, elapsed_ms=elapsed)
        outputs.append(product.model_dump(mode="json"))
        print(f"    {index + 1}/{runs} 완료 ({elapsed}ms)", file=sys.stderr)
    return outputs


def print_report(report: FixtureReport) -> None:
    counts = report.counts()
    graded = counts["graded_fields"]
    print(f"\n### {report.fixture}  ({report.runs}회 실행, 채점 {graded}개 / 미채점 {counts['ungraded_fields']}개)")
    print(f"  C1 치명 {counts['c1']}  C2 미탐 {counts['c2']}  C3 오탐 {counts['c3']}")
    print(f"  안정정답 {counts['stable_ok']}  안정오답 {counts['stable_wrong']}  불안정 {counts['unstable']}"
          f"  (확정끼리 진동 {counts['hard_flip']})")

    problems = [f for f in report.fields if f.worst is not Grade.OK or f.stability is Stability.UNSTABLE]
    if not problems:
        print("  문제 없음")
        return
    for field in sorted(problems, key=lambda f: (f.stability is not Stability.STABLE_WRONG, f.name)):
        flag = "!" if field.hard_flip else " "
        print(f"  {flag} {field.name:26s} 정답={field.truth!r:>7} 실행={field.values} "
              f"[{field.worst.value}/{field.stability.value}]")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="추출 에이전트 평가")
    parser.add_argument("--fixture", action="append", default=[], help="정답표 이름(확장자 제외)")
    parser.add_argument("--all", action="store_true", help="정답표가 있는 픽스처 전부")
    parser.add_argument("--runs", type=int, default=5, help="픽스처당 실행 횟수 (기본 5)")
    parser.add_argument("--rescore", type=Path, help="저장된 실행 결과를 재채점만 한다")
    args = parser.parse_args()

    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        for name, outputs in saved["results"].items():
            truth = load_truth(TRUTH_DIR / f"{name}.json")
            print_report(score(truth, [o for o in outputs if not o.get("_failed")]))
        return 0

    names = [p.stem for p in sorted(TRUTH_DIR.glob("*.json"))] if args.all else args.fixture
    if not names:
        parser.error("--all 또는 --fixture 를 지정하세요.")

    # 모델을 만들기 전에 원문이 다 있는지 먼저 본다. 뒤쪽 픽스처가 없으면
    # 앞쪽에 쓴 API 호출이 통째로 낭비된다.
    missing = [n for n in names if not (RAW_DIR / load_truth(TRUTH_DIR / f"{n}.json")["fixture"]).exists()]
    if missing:
        print(f"원문 픽스처가 없습니다: {', '.join(missing)}", file=sys.stderr)
        print(f"저장소에는 축약본만 들어 있습니다. 원문을 {RAW_DIR} 에 넣어주세요 "
              f"(tests/fixtures/README.md 참고).", file=sys.stderr)
        return 1

    agent = ExtractionAgent()
    results: dict[str, list[dict]] = {}
    for name in names:
        truth = load_truth(TRUTH_DIR / f"{name}.json")
        print(f"  {truth['fixture']} x{args.runs}", file=sys.stderr)
        results[name] = run_fixture(agent, truth["fixture"], args.runs)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULT_DIR / f"{stamp}.json"
    out.write_text(json.dumps({"runs": args.runs, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    for name, outputs in results.items():
        truth = load_truth(TRUTH_DIR / f"{name}.json")
        ok_runs = [o for o in outputs if not o.get("_failed")]
        if not ok_runs:
            print(f"\n### {name}: 전 회차 실패")
            continue
        print_report(score(truth, ok_runs))
    print(f"\n실행 결과 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
