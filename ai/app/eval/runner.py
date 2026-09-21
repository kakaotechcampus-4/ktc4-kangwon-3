"""픽스처를 N회 추출해 정답표와 대조한다.

    python -m app.eval.runner --all --runs 5
    python -m app.eval.runner --fixture power_bank --runs 3
    python -m app.eval.runner --rescore logs/eval/20260916-014923.json  (재호출 없이 다시 채점)

실행 결과 원본을 항상 파일로 남긴다. 채점 기준을 고치면 LLM을 다시 부르지 않고
같은 데이터로 재채점할 수 있어야 기준을 마음 놓고 다듬을 수 있다.

결과 파일에는 "무엇으로 쟀는지"(meta)를 함께 적는다. 프롬프트가 바뀌면 이전 수치와
비교하면 안 되는데, 기록이 없으면 그 사실을 알 방법이 없다.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 프롬프트 경로는 에이전트가 실제로 읽는 것과 반드시 같아야 한다. 여기서 경로를 다시
# 적으면 한쪽만 옮겨졌을 때 "다른 프롬프트로 잰 결과"를 같은 것으로 착각하게 된다.
from ..agents.extraction import _PROMPT_PATH as EXTRACTION_PROMPT_PATH
from ..agents.extraction import ExtractionAgent, ExtractionFailedError
from ..config import DEFAULT_MODEL, load_settings
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


def prompt_fingerprint(path: Path | None = None) -> str:
    """추출 프롬프트의 SHA-256. 한 글자만 달라도 값이 바뀐다.

    줄바꿈은 LF로 맞춰서 잰다. 같은 내용인데 윈도우(CRLF)와 CI(LF)에서 다른 값이
    나오면 "프롬프트가 바뀌었다"는 잘못된 경고가 뜬다.
    """
    target = path or EXTRACTION_PROMPT_PATH
    normalized = target.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _git(*args: str) -> str | None:
    """git 명령 결과. git이 없거나 저장소가 아니면 None을 돌려주고 넘어간다."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=_AI_ROOT, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def run_metadata(*, runs: int, model: str) -> dict:
    """이번 측정이 "무엇으로" 나온 값인지 기록한다.

    프롬프트가 바뀌면 이전 수치와 비교하면 안 된다. 사람이 버전을 적는 방식은
    까먹지만 파일 지문은 틀리지 않으므로 해시를 남긴다.
    """
    # 범위를 ai/ 로 제한한다. 제한하지 않으면 다른 팀의 커밋 안 된 파일까지 잡혀서
    # 늘 "수정 있음"이 뜨고, 결국 경고를 무시하게 된다.
    dirty = _git("status", "--porcelain", "--", ".")
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        # 커밋 해시만으로는 부족하다. 커밋하지 않은 수정이 있으면 그 해시의 코드가 아니다.
        "git_dirty": None if dirty is None else bool(dirty),
        "model": model,
        "prompt_path": EXTRACTION_PROMPT_PATH.relative_to(_AI_ROOT).as_posix(),
        "prompt_sha256": prompt_fingerprint(),
        "runs": runs,
    }


def describe_metadata(meta: dict) -> str:
    """사람이 읽는 한 줄 요약."""
    # 손으로 편집했거나 형식이 다른 기록도 읽을 수 있어야 한다. 요약 한 줄 때문에
    # 재채점 전체가 죽으면 안 된다.
    dirty = " (커밋 안 된 수정 있음)" if meta.get("git_dirty") else ""
    fingerprint = (meta.get("prompt_sha256") or "알 수 없음")[:12]
    return (
        f"모델 {meta.get('model') or '알 수 없음'} / "
        f"커밋 {meta.get('git_commit') or '알 수 없음'}{dirty} / "
        f"프롬프트 {fingerprint} / {meta.get('runs', '?')}회"
    )


def run_fixture(
    agent: ExtractionAgent, name: str, runs: int, model: str = DEFAULT_MODEL
) -> list[dict]:
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
            record("extraction-eval", None, configured_model=model,
                   subject_id=source.product_id, ok=False, elapsed_ms=elapsed,
                   error_type=type(exc.__cause__ or exc).__name__)
            outputs.append({"_failed": True, "_error": str(exc)})
            print(f"    {index + 1}/{runs} 실패: {exc}", file=sys.stderr)
            continue
        elapsed = int((time.perf_counter() - started) * 1000)
        record("extraction-eval", None, configured_model=model,
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


def warn_if_prompt_changed(meta: dict | None) -> list[str]:
    """저장된 결과가 지금 프롬프트로 나온 값인지 확인하고 경고 문구를 돌려준다.

    비교하면 안 되는 두 측정치를 나란히 놓는 것이 이 평가에서 제일 흔한 사고다.
    """
    if not meta:
        return ["[주의] 메타 정보가 없는 결과입니다. 어떤 프롬프트로 나온 값인지 알 수 없습니다."]
    saved = meta.get("prompt_sha256")
    if not saved:
        return ["[주의] 기록에 프롬프트 지문이 없습니다. 같은 프롬프트로 잰 값인지 알 수 없습니다."]
    current = prompt_fingerprint()
    if saved != current:
        return [
            f"[주의] 지금과 다른 프롬프트로 나온 결과입니다 "
            f"(기록 {saved[:12]} / 현재 {current[:12]}). 같은 기준선으로 비교하면 안 됩니다."
        ]
    return []


def rescore(path: Path) -> int:
    """저장된 실행 결과를 LLM 재호출 없이 다시 채점한다."""
    saved = json.loads(path.read_text(encoding="utf-8"))
    meta = saved.get("meta")
    for line in warn_if_prompt_changed(meta):
        print(line, file=sys.stderr)
    if meta:
        print(f"측정 조건: {describe_metadata(meta)}", file=sys.stderr)
    for name, outputs in saved["results"].items():
        truth = load_truth(TRUTH_DIR / f"{name}.json")
        print_report(score(truth, [o for o in outputs if not o.get("_failed")]))
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="추출 에이전트 평가")
    parser.add_argument("--fixture", action="append", default=[], help="정답표 이름(확장자 제외)")
    parser.add_argument("--all", action="store_true", help="정답표가 있는 픽스처 전부")
    parser.add_argument("--runs", type=int, default=5, help="픽스처당 실행 횟수 (기본 5)")
    parser.add_argument("--rescore", type=Path, help="저장된 실행 결과를 재채점만 한다")
    args = parser.parse_args()

    if args.rescore:
        return rescore(args.rescore)

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
    # ExtractionAgent()가 설정을 이미 검증했으므로 여기서 다시 읽어도 실패하지 않는다.
    meta = run_metadata(runs=args.runs, model=load_settings().model)
    print(f"측정 조건: {describe_metadata(meta)}", file=sys.stderr)
    if meta["git_dirty"]:
        print("  커밋하지 않은 수정이 있습니다. 기록된 커밋만으로는 재현되지 않습니다.",
              file=sys.stderr)

    results: dict[str, list[dict]] = {}
    for name in names:
        truth = load_truth(TRUTH_DIR / f"{name}.json")
        print(f"  {truth['fixture']} x{args.runs}", file=sys.stderr)
        results[name] = run_fixture(agent, truth["fixture"], args.runs, meta["model"])

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULT_DIR / f"{stamp}.json"
    out.write_text(
        json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

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
