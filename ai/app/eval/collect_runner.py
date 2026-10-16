"""상품 주소로 수집 → 이미지 분류 → 추출을 돌려, 추출에 넣는 이미지 방식별 결과를 나란히 저장한다.

    cd ai
    python -m app.eval.collect_runner --url <상품 주소> [--url ...] --runs 2
    python -m app.eval.collect_runner --url <상품 주소> --html <저장한 HTML> [--url ... --html ...]
    python -m app.eval.collect_runner --summarize data/collect_probe/made_in_china/<상품 ID>

상품마다 한 번 수집·분류하고, 같은 판매자 글로 방식마다 runs번 추출한다.
    - text: 이미지 없이 판매자 글만
    - all: 후보 이미지 전체 (원본 크기)
    - selected: 고른 이미지 (url_source.select_images)
정답 채점은 하지 않음. 방식별로 달라진 칸과 판매자 글에 없는 근거(이미지에서 온 값)를 summary.md로 뽑아
사람이 그 부분만 원문과 대조하게 함. 원문 페이지는 ai/data/(커밋하지 않음)에만 저장.
--html을 주면 페이지를 받지 않고 그 HTML로 돌림 (같은 입력으로 다시 재기, 사이트가 응답하지 않을 때 재현).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from ..agents.extraction import PROMPT_PATH as EXTRACTION_PROMPT_PATH
from ..agents.extraction import ExtractionAgent, ExtractionFailedError
from ..agents.image_triage import ImageTriageAgent
from ..config import agent_profile
from ..pipeline.url_source import MAX_ALL_IMAGES, UrlSource, UrlSourceBuilder, client_for
from ..schemas.agent import ExtractionInput
from ..schemas.clients.marketplace_request import ProductPageRequest
from .. import usage
from .runner import _AI_ROOT, describe_metadata, run_metadata

OUT_DIR = _AI_ROOT / "data" / "collect_probe"
MODES = ("text", "all", "selected")
# 상품 정보 중 방식별로 비교할 판단 칸. 목록·속성은 따로 봄
_SKIP_FIELDS = {"product_id", "source_url", "listing_text", "attributes", "conflicts"}


def product_key(url: str) -> str:
    """저장 폴더 이름. Made-in-China는 주소의 상품 ID, 그 밖에는 경로 끝."""
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "product":
        return parts[1]
    return re.sub(r"[^A-Za-z0-9_-]", "_", parts[-1] if parts else urlparse(url).hostname or "page")[:60]


def mode_input(source: UrlSource, mode: str, product_id: str) -> ExtractionInput:
    """방식별 추출 입력. 판매자 글은 같고 이미지만 다름."""
    images = {
        "text": [],
        "all": [image.url for image in source.page.images][:MAX_ALL_IMAGES],
        "selected": [image.url for image in source.selected],
    }[mode]
    return source.extraction_input.model_copy(update={"product_id": product_id, "image_urls": images})


def usage_of(subject_id: str, log: Path | None = None) -> dict:
    """사용량 로그에서 이 대상의 호출을 합친다. 대상 ID는 실행마다 다르게 붙임.

    Args:
        subject_id: 사용량 기록 대상 ID.
        log: 사용량 로그. None이면 지금 설정된 공용 로그 (테스트에서 바꾼 경로도 따름).

    Returns:
        dict: 호출 수·입력·출력 토큰·추정 비용 합.
    """
    log = log or usage.USAGE_LOG
    rows = []
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("subject_id") == subject_id:
                rows.append(row)
    return {
        "calls": len(rows),
        "input_tokens": sum(row.get("input_tokens") or 0 for row in rows),
        "output_tokens": sum(row.get("output_tokens") or 0 for row in rows),
        "estimated_cost_krw": round(sum(row.get("estimated_cost_krw") or 0 for row in rows), 2),
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def image_sourced_attributes(product: dict, text_blocks: list[str]) -> list[dict]:
    """근거(source_text)가 판매자 글에 없는 속성. 이미지에서 왔거나 지어낸 값 후보."""
    corpus = _normalize("\n".join(text_blocks))
    return [attribute for attribute in product.get("attributes", [])
            if attribute.get("source_text") and _normalize(attribute["source_text"]) not in corpus]


def compare_fields(results: dict[str, list[dict | None]]) -> list[tuple[str, dict[str, list]]]:
    """판단 칸별로 방식·회차 값을 모은다. 값이 하나라도 다른 칸만 돌려줌.

    Args:
        results: 방식 → 회차별 추출 결과(dict). 실패한 회차는 None.

    Returns:
        list[tuple[str, dict[str, list]]]: (칸 이름, 방식 → 회차별 값).
    """
    fields = sorted({key for runs in results.values() for product in runs if product
                     for key in product if key not in _SKIP_FIELDS})
    rows = []
    for field in fields:
        values = {mode: [product.get(field) if product else "실패" for product in runs] for mode, runs in results.items()}
        if len({json.dumps(value, ensure_ascii=False) for runs in values.values() for value in runs}) > 1:
            rows.append((field, values))
    return rows


def run_product(
    url: str, builder: UrlSourceBuilder, extractor: ExtractionAgent, *, runs: int, out: Path, html: Path | None = None,
) -> Path:
    """상품 하나: 수집·분류 한 번, 방식마다 runs번 추출하고 저장한다. html을 주면 페이지를 받지 않음."""
    key = product_key(url)
    # 사용량을 대상 ID로 모으므로 실행마다 다른 ID. 같은 상품을 다시 돌려도 앞 실행 비용이 섞이지 않음
    prefix = f"collect:{key}:{uuid4().hex[:8]}"
    if html is None:
        client = client_for(url)
        try:
            raw_html = client.fetch_raw(ProductPageRequest(url=url)).text
        finally:
            client.close()
    else:
        raw_html = html.read_text(encoding="utf-8")
    started = time.monotonic()
    # 받은 HTML 하나로 저장·파싱을 같이 해 두 번 요청하지 않음
    source = builder.build_from_html(url, raw_html, product_id=f"{prefix}:triage")
    triage_seconds = round(time.monotonic() - started, 1)

    directory = out / source.page.site / key
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "raw.html").write_text(raw_html, encoding="utf-8")
    _dump(directory / "page.json", source.page.model_dump(mode="json"))
    _dump(directory / "triage.json", {
        "items": [{**item.model_dump(mode="json"), "url": source.page.images[item.index - 1].url}
                  for item in source.triage.items],
        "selected": [image.url for image in source.selected],
    })
    meta = {"url": url, "input": str(html) if html else "live", "final_url": source.page.source_url,
            "triage": {"seconds": triage_seconds, **usage_of(f"{prefix}:triage")}, "modes": {}}

    for mode in MODES:
        for run in range(1, runs + 1):
            run_dir = directory / mode / f"run_{run}"
            run_dir.mkdir(parents=True, exist_ok=True)
            subject = f"{prefix}:{mode}:{run}"
            extraction_input = mode_input(source, mode, subject)
            _dump(run_dir / "extraction_input.json", extraction_input.model_dump(mode="json"))
            started = time.monotonic()
            try:
                product = extractor.extract(extraction_input).model_dump(mode="json")
            except ExtractionFailedError as exc:
                product = {"_failed": type(exc.__cause__ or exc).__name__}
            _dump(run_dir / "product.json", product)
            meta["modes"].setdefault(mode, []).append({
                "run": run, "images": len(extraction_input.image_urls),
                "seconds": round(time.monotonic() - started, 1), **usage_of(subject)})
            last = meta["modes"][mode][-1]
            print(f"  {mode:<8} {run}회: 이미지 {last['images']}장, {last['seconds']}s, "
                  f"{last['estimated_cost_krw']}원", flush=True)
    _dump(directory / "meta.json", meta)
    write_summary(directory)
    return directory


def write_summary(directory: Path) -> Path:
    """저장된 결과로 summary.md를 만든다. 다시 돌리지 않고 요약만 새로 쓸 때도 씀."""
    page = json.loads((directory / "page.json").read_text(encoding="utf-8"))
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    results: dict[str, list[dict | None]] = {}
    for mode in MODES:
        for run_dir in sorted((directory / mode).glob("run_*")):
            product = json.loads((run_dir / "product.json").read_text(encoding="utf-8"))
            results.setdefault(mode, []).append(None if "_failed" in product else product)

    lines = [f"# {page.get('title') or directory.name}", "", f"- 주소: {meta['url']}",
             f"- 판매자 글 {len(page['text_blocks'])}줄, 후보 이미지 {len(page['images'])}장", ""]
    lines += ["## 비용·시간", "", "| 단계 | 회차 | 이미지 | 입력 토큰 | 출력 토큰 | 비용(원) | 시간(초) |", "|---|---|---|---|---|---|---|"]
    triage = meta["triage"]
    lines.append(f"| 분류 | 1 | {len(page['images'])} | {triage['input_tokens']} | {triage['output_tokens']} "
                 f"| {triage['estimated_cost_krw']} | {triage['seconds']} |")
    for mode, runs in meta["modes"].items():
        for run in runs:
            lines.append(f"| {mode} | {run['run']} | {run['images']} | {run['input_tokens']} | {run['output_tokens']} "
                         f"| {run['estimated_cost_krw']} | {run['seconds']} |")

    lines += ["", "## 방식·회차마다 값이 다른 판단 칸", ""]
    rows = compare_fields(results)
    if rows:
        lines += ["| 칸 | " + " | ".join(results) + " |", "|---|" + "---|" * len(results)]
        for field, values in rows:
            cells = [" / ".join(json.dumps(value, ensure_ascii=False) for value in values[mode]) for mode in results]
            lines.append(f"| {field} | " + " | ".join(cells) + " |")
    else:
        lines.append("모든 방식·회차가 같음")

    lines += ["", "## 판매자 글에 없는 근거로 뽑힌 속성 (이미지에서 왔거나 지어낸 값 후보)", ""]
    found = False
    for mode, runs in results.items():
        for run, product in enumerate(runs, 1):
            for attribute in image_sourced_attributes(product or {}, page["text_blocks"]):
                found = True
                lines.append(f"- {mode} {run}회: **{attribute['name']}** = {attribute['value']} "
                             f"(근거: {attribute['source_text']})")
    if not found:
        lines.append("없음 (모든 속성의 근거가 판매자 글)")
    path = directory / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="상품 주소 수집·이미지 선별·추출 실험")
    parser.add_argument("--url", action="append", default=[], help="상품 페이지 주소 (여러 번 줄 수 있음)")
    parser.add_argument("--html", type=Path, action="append", default=[],
                        help="--url 순서대로 쓸 저장한 HTML. 주면 페이지를 받지 않음 (url 개수와 같아야 함)")
    parser.add_argument("--runs", type=int, default=2, help="방식마다 추출 회차 (기본 2)")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--summarize", type=Path, help="저장된 상품 폴더의 summary.md만 다시 만든다")
    args = parser.parse_args()

    if args.summarize:
        print(f"요약: {write_summary(args.summarize)}")
        return 0
    if not args.url:
        parser.error("--url 또는 --summarize 를 지정하세요.")
    if args.html and len(args.html) != len(args.url):
        parser.error("--html은 --url과 같은 개수로, 같은 순서로 지정하세요.")

    # 평가 호출은 운영 사용량과 나눠 집계
    # 세 방식을 모두 비교하려고 사이트 설정과 관계없이 분류까지 함
    builder = UrlSourceBuilder(ImageTriageAgent(usage_agent="image_triage-eval"), images="selected")
    extractor = ExtractionAgent(usage_agent="extraction-eval")
    meta = run_metadata(runs=args.runs, profile=agent_profile("extraction"), prompt_path=EXTRACTION_PROMPT_PATH)
    print(describe_metadata(meta))
    failed = []
    for url, html in zip(args.url, args.html or [None] * len(args.url)):
        print(f"\n{url}" + (f" (저장한 HTML: {html})" if html else ""))
        try:
            directory = run_product(url, builder, extractor, runs=args.runs, out=args.out, html=html)
        except Exception as exc:
            # 한 상품의 수집·분류 실패(시간 초과·차단 등)로 나머지 상품까지 멈추지 않게 기록만
            print(f"  실패: {type(exc).__name__}: {exc}")
            failed.append(url)
            continue
        _dump(directory / "run_meta.json", meta)
        print(f"  저장: {directory} (요약 summary.md)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
