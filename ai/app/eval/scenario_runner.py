"""사용자 시나리오 끝단 평가: 실제 상품 원문 → 추출 → 선택을 돌려 선택 정답과 대조한다.

    cd ai
    python -m app.eval.scenario_runner --truth-dir <정답 폴더> --raw-dir <원문 폴더> [--extraction-truth-dir <추출 정답 폴더>]
        [--input-file text_as_pasted.txt] [--runs 3] [--retries 2] --report <보고서.md> --title "개발 표본 (펼친 글)"
    python -m app.eval.scenario_runner --rescore logs/eval/scenario-<시각>.json [--truth-dir <정답 폴더>] --report <보고서.md> --title "..."

상품마다 추출 N회 → 추출 결과마다 선택 1회. 실패한 회차는 최대 retries번 다시 시도하고, 그래도 실패하면 빈 회차로
남겨 채점에서 "골라야 할 Tool 전부 빠뜨림"으로 센다. 원문은 --raw-dir로 직접 가리킨다(워크트리에 링크를 만들지 않음).
문서: docs/current/eval/SCENARIO_EVAL.md
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..agents.extraction import ExtractionAgent, ExtractionFailedError
from ..agents.selection import PROMPT_PATH as SELECTION_PROMPT_PATH
from ..agents.selection import SelectionAgent, SelectionFailedError
from ..config import agent_profile
from ..schemas.agent import ExtractionInput
from ..schemas.product import Product
from .errors import RawFixtureMissing
from .runner import RESULT_DIR, prompt_fingerprint, run_metadata
from .scenario_scoring import render_report, summarize
from .scoring import load_truth
from .selection_scoring import load_selection_truth

MAX_WORKERS = 4


@dataclass(frozen=True)
class ProductInput:
    """상품 하나의 입력. fallback은 요청한 입력 파일이 없어 펼친 글(text.txt)로 대신했는지."""

    name: str
    text_path: Path
    fallback: bool


def plan_products(truth_dir: Path, raw_dir: Path, input_file: str) -> list[ProductInput]:
    """선택 정답마다 원문 파일을 정한다. 원문 폴더가 하나라도 없으면 모델을 만들기 전에 멈춘다.

    Raises:
        RawFixtureMissing: 정답이 가리키는 원문 폴더나 text.txt가 없는 경우.
    """
    items: list[ProductInput] = []
    missing: list[str] = []
    for path in sorted(truth_dir.glob("*.json")):
        truth = load_selection_truth(path)
        folder = raw_dir / Path(truth["fixture"]).parent
        wanted, default = folder / input_file, folder / "text.txt"
        if wanted.exists():
            items.append(ProductInput(path.stem, wanted, False))
        elif default.exists():
            items.append(ProductInput(path.stem, default, True))
        else:
            missing.append(f"{path.stem} → {folder}")
    if missing:
        raise RawFixtureMissing("원문이 없습니다: " + ", ".join(missing))
    return items


def _with_retry(call, retries: int, errors: tuple[type[Exception], ...]):
    """call을 실패 시 retries번까지 다시 부른다. (결과 또는 None, 다시 시도한 횟수)."""
    for attempt in range(retries + 1):
        try:
            return call(), attempt
        except errors as exc:
            print(f"      실패({attempt + 1}/{retries + 1}): {str(exc)[:120]}", file=sys.stderr)
    return None, retries


def run_product(extractor, selector, item: ProductInput, runs: int, retries: int) -> dict:
    """상품 하나를 runs번 추출하고, 추출 결과마다 한 번 선택한다."""
    text = item.text_path.read_text(encoding="utf-8")
    result: dict = {"runs": [], "retries": 0, "input_fallback": item.fallback, "input": item.text_path.name}
    for index in range(runs):
        source = ExtractionInput(product_id=f"scenario-{item.name}-{index}", text_blocks=[text])
        product, extract_retries = _with_retry(
            lambda: extractor.run(source).model_dump(mode="json"), retries, (ExtractionFailedError,)
        )
        result["retries"] += extract_retries
        selection = None
        if product is not None:
            selection, select_retries = _with_retry(
                lambda: selector.run(Product.model_validate({**product, "product_id": source.product_id})).model_dump(mode="json"),
                retries, (SelectionFailedError,),
            )
            result["retries"] += select_retries
        result["runs"].append({"extracted": product, "selection": selection})
    print(f"  {item.name} 완료 ({item.text_path.name})", file=sys.stderr)
    return result


def build_agents() -> tuple[ExtractionAgent, SelectionAgent, dict]:
    """운영 기본 프로필의 추출·선택 에이전트와 측정 조건."""
    extractor = ExtractionAgent(usage_agent="scenario-eval")
    selector = SelectionAgent(usage_agent="scenario-eval")
    meta = run_metadata(runs=0, profile=agent_profile("extraction"))
    meta["selection_model"] = agent_profile("selection").model.id
    meta["selection_prompt_sha256"] = prompt_fingerprint(SELECTION_PROMPT_PATH)
    return extractor, selector, meta


def _load_truths(truth_dir: Path, extraction_truth_dir: Path | None, names: list[str]) -> tuple[dict, dict]:
    truths = {name: load_selection_truth(truth_dir / f"{name}.json") for name in names}
    extraction: dict[str, dict | None] = {}
    for name in names:
        match = sorted(extraction_truth_dir.glob(f"{name}_*.json")) if extraction_truth_dir else []
        extraction[name] = load_truth(match[0]) if match else None
    return truths, extraction


def _write_report(path: Path | None, summary: dict, meta: dict, title: str) -> None:
    text = render_report(summary, meta, title)
    if path:
        path.write_text(text, encoding="utf-8")
    print(text)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="사용자 시나리오 끝단 평가 (추출 → 선택)")
    parser.add_argument("--truth-dir", type=Path, help="선택 정답 폴더 (재채점에서 주면 저장된 경로 대신 씀)")
    parser.add_argument("--raw-dir", type=Path, help="원문 폴더 (정답 fixture 경로의 기준)")
    parser.add_argument("--extraction-truth-dir", type=Path, help="추출 정답 폴더 (있으면 빠뜨림 원인을 분류)")
    parser.add_argument("--input-file", default="text.txt", help="상품 폴더 안의 입력 파일 (기본 text.txt)")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--report", type=Path, help="보고서 마크다운 경로")
    parser.add_argument("--title", default="시나리오 평가")
    parser.add_argument("--rescore", type=Path, help="저장된 결과 JSON을 재채점만 한다")
    args = parser.parse_args(argv)

    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        # 저장된 경로는 측정한 PC 기준이라, 다른 PC에서는 --truth-dir·--extraction-truth-dir로 다시 가리킨다
        truth_dir = args.truth_dir or Path(saved["truth_dir"])
        etd = args.extraction_truth_dir or (Path(saved["extraction_truth_dir"]) if saved.get("extraction_truth_dir") else None)
        truths, extraction = _load_truths(truth_dir, etd, list(saved["products"]))
        _write_report(args.report, summarize(saved["products"], truths, extraction), saved["meta"], args.title)
        return 0

    if not args.truth_dir or not args.raw_dir:
        parser.error("--truth-dir와 --raw-dir가 필요합니다 (재채점은 --rescore).")
    if args.extraction_truth_dir and not args.extraction_truth_dir.is_dir():
        # 경로를 잘못 주면 원인 분류가 조용히 전부 '분류 안 함'이 된다. 모델을 돌리기 전에 멈춘다.
        parser.error(f"--extraction-truth-dir 폴더가 없습니다: {args.extraction_truth_dir}")
    items = plan_products(args.truth_dir, args.raw_dir, args.input_file)
    # 정답표 형식 오류도 모델을 돌리기 전에 잡는다.
    truths, extraction = _load_truths(args.truth_dir, args.extraction_truth_dir, [i.name for i in items])
    extractor, selector, meta = build_agents()
    meta["runs"] = args.runs
    print(f"상품 {len(items)}개 × {args.runs}회, 입력 {args.input_file}", file=sys.stderr)

    def safe_run(item: ProductInput) -> dict:
        # 재시도하지 않는 예외(빈 구역의 ValueError, 규칙 코드 버그 등) 하나로 전체 결과를 잃지 않게,
        # 그 상품만 전 회차 실패로 남긴다. 실패 회차는 채점에서 '전부 빠뜨림'이라 숫자가 부풀지 않는다.
        try:
            return run_product(extractor, selector, item, args.runs, args.retries)
        except Exception as exc:  # noqa: BLE001
            print(f"  {item.name} 예상 밖 실패: {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)
            return {"runs": [{"extracted": None, "selection": None} for _ in range(args.runs)], "retries": 0,
                    "input_fallback": item.fallback, "input": item.text_path.name, "error": type(exc).__name__}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(safe_run, items))
    products = {item.name: result for item, result in zip(items, results)}

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"scenario-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({
        "meta": meta, "truth_dir": str(args.truth_dir), "raw_dir": str(args.raw_dir),
        "extraction_truth_dir": str(args.extraction_truth_dir) if args.extraction_truth_dir else None,
        "input_file": args.input_file, "products": products,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_report(args.report, summarize(products, truths, extraction), meta, args.title)
    print(f"\n실행 결과 저장: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
