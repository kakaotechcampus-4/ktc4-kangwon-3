"""별표 파싱 에이전트를 실제 모델로 돌려 원문 대조·정답 채점·토큰·시간을 잰다.

    python -m app.eval.annex_runner                                   # 픽스처 전부, .env 모델
    python -m app.eval.annex_runner --fixture 전기용품및생활용품안전관리운용요령_별표0004-00
    python -m app.eval.annex_runner --model openai/gpt-6-luna#low       # 모델 이름#추론 강도
    python -m app.eval.annex_runner --rescore logs/eval/annex-20261012-120000.json

픽스처는 tests/fixtures/annex/, 정답셋은 tests/eval_truth_annex/ (정답이 없으면 원문 대조만).
서비스 설정의 허용 모델(ALLOWED_MODELS)은 바꾸지 않음. 다른 모델은 이 스크립트에서만 만듦.
비용이 듦. 별표 하나가 조각 여러 개면 조각마다 호출.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from time import perf_counter

from .. import usage as usage_module
from ..agents import base as agent_base
from ..agents.annex_parsing import AnnexParsingAgent, AnnexParsingError
from ..config import MAX_RETRIES, TIMEOUT_SECONDS, build_chat_model, load_settings
from ..prompts import PromptName, get_prompt
from ..schemas.agents.annex import AnnexParseOutput, AnnexSource
from ..utils.annex_text import compact_annex, split_annex
from .annex_scoring import ANNEX_TRUTH_DIR, AnnexScore, load_annex_truth, score_annex
from .runner import RESULT_DIR, describe_metadata, run_metadata

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "annex"
# usage.PRICING_KRW에 없는 모델 단가 (1M 토큰당 원, #279)
_EXTRA_PRICES = {"openai/gpt-6-luna": {"input": 152.0, "cached_input": 15.0, "output": 761.0}}


def build_model(spec: str | None):
    """'이름[#추론강도]'로 모델을 만든다. None이면 서비스 설정(build_chat_model).

    추론 모델은 temperature를 받지 않아 보내지 않음. 스트리밍·타임아웃은 서비스와 같음.

    Returns:
        tuple: (모델 이름, 모델).
    """
    if spec is None:
        return load_settings().model, build_chat_model()
    from langchain_openai import ChatOpenAI

    name, _, effort = spec.partition("#")
    settings = load_settings()
    options = {"reasoning_effort": effort} if effort else {"temperature": 0}
    return name, ChatOpenAI(
        model=name, base_url=settings.base_url, api_key=settings.api_key, **options,
        timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES, streaming=True, stream_usage=True,
    )


def _cost(call: dict, model: str) -> float | None:
    price = usage_module.PRICING_KRW.get(model) or _EXTRA_PRICES.get(model)
    if price is None or call["input_tokens"] is None:
        return None
    uncached = call["input_tokens"] - call["cached_tokens"]
    return (uncached * price["input"] + call["cached_tokens"] * price["cached_input"]
            + call["output_tokens"] * price["output"]) / 1_000_000


class _UsageCapture:
    """에이전트가 남기는 사용량 기록을 가로채 별표별로 모은다. 원래 로그에도 그대로 씀."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._original = agent_base.record

    def __enter__(self) -> "_UsageCapture":
        def capture(agent, call_usage, **kwargs):
            self.calls.append({
                "input_tokens": call_usage.input_tokens if call_usage else None,
                "cached_tokens": call_usage.cached_tokens if call_usage else None,
                "output_tokens": call_usage.output_tokens if call_usage else None,
                "elapsed_ms": kwargs.get("elapsed_ms"),
                "ok": kwargs.get("ok", True),
                "error_type": kwargs.get("error_type"),
            })
            self._original(agent, call_usage, **kwargs)

        agent_base.record = capture
        return self

    def __exit__(self, *exc) -> None:
        agent_base.record = self._original


def run_fixture(agent: AnnexParsingAgent, name: str, model: str) -> dict:
    """픽스처 하나를 파싱한다. 실패해도 기록을 남기고 다음으로 넘어감."""
    meta = json.loads((FIXTURE_DIR / name / "meta.json").read_text(encoding="utf-8"))
    source = AnnexSource.model_validate(meta["source"])
    content = (FIXTURE_DIR / name / "content.txt").read_text(encoding="utf-8")
    chunks = len(split_annex(compact_annex(content)))
    started = perf_counter()
    record = error = None
    with _UsageCapture() as captured:
        try:
            record = agent.parse(source, content)
        except AnnexParsingError as exc:
            error = f"{exc} ← {type(exc.__cause__).__name__}"
    for call in captured.calls:
        call["cost_krw"] = _cost(call, model)
    return {
        "fixture": name,
        "chunks": chunks,
        "seconds": round(perf_counter() - started, 1),
        "calls": captured.calls,
        "error": error,
        "record": record.model_dump(mode="json") if record else None,
    }


def _score(result: dict) -> AnnexScore | None:
    truth_path = ANNEX_TRUTH_DIR / f"{result['fixture']}.json"
    if not truth_path.exists() or not result["record"] or not result["record"]["output"]:
        return None
    _, truth = load_annex_truth(truth_path)
    return score_annex(truth, AnnexParseOutput.model_validate(result["record"]["output"]))


def report(results: list[dict]) -> None:
    """별표별 한 줄 요약과 실패 사유·채점 오류를 출력한다."""
    total_cost = 0.0
    for result in results:
        calls = result["calls"]
        output_tokens = sum(call["output_tokens"] or 0 for call in calls)
        max_output = max((call["output_tokens"] or 0 for call in calls), default=0)
        cost = sum(call.get("cost_krw") or 0 for call in calls)
        total_cost += cost
        record = result["record"] or {}
        status = "오류" if result["error"] else ("통과" if record.get("verified") else "대조 실패")
        rows = len((record.get("output") or {}).get("items", []))
        print(f"\n## {result['fixture']}")
        print(f"  {status} · 조각 {result['chunks']} · 호출 {len(calls)} · 행 {rows} · {result['seconds']}s · "
              f"출력 토큰 {output_tokens} (조각 최대 {max_output}) · {cost:.1f}원")
        if result["error"]:
            print(f"  ! {result['error']}")
        for reason in record.get("failure_reasons", [])[:10]:
            print(f"  - {reason}")
        score = _score(result)
        if score is not None:
            print(f"  정답 {score.expected_rows}행 중 일치 {score.matched_rows} · 초과 {len(score.extra)} · "
                  f"분류 오류 {len(score.category_errors)} · 문구 오류 {len(score.field_errors)} · "
                  f"구분 {'O' if score.scheme_ok else 'X'} · 뺀 행 {'O' if score.skipped_ok else 'X'} · "
                  f"공통 비고 {'O' if score.notes_ok else 'X'}")
            for label, rows_ in (("누락", score.missing), ("초과", score.extra),
                                 ("분류", score.category_errors), ("문구", score.field_errors)):
                for row in rows_[:5]:
                    print(f"    {label}: {row}")
    print(f"\n합계 {total_cost:.1f}원")


def rescore(path: Path) -> int:
    """저장한 결과를 지금 정답셋으로 다시 채점한다. API 호출 없음."""
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"측정 조건: {describe_metadata(data['meta'])}")
    report(data["results"])
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="별표 파싱 에이전트 평가")
    parser.add_argument("--fixture", action="append", default=[], help="픽스처 디렉터리 이름 (여러 번 가능)")
    parser.add_argument("--model", help="모델 이름[#추론강도]. 없으면 .env 모델")
    parser.add_argument("--rescore", type=Path, help="저장된 결과를 재채점만 한다")
    args = parser.parse_args()
    if args.rescore:
        return rescore(args.rescore)

    names = args.fixture or sorted(path.name for path in FIXTURE_DIR.iterdir() if path.is_dir())
    missing = [name for name in names if not (FIXTURE_DIR / name / "content.txt").exists()]
    if missing:
        parser.error(f"픽스처가 없습니다: {', '.join(missing)}")

    model_name, model = build_model(args.model)
    # 평가 비용이 운영 비용과 섞이지 않게 사용량 이름을 나눔
    agent = AnnexParsingAgent(model=model, configured_model=model_name, usage_agent="annex-parsing-eval")
    meta = run_metadata(runs=1, model=args.model or model_name, prompt_path=get_prompt(PromptName.ANNEX_PARSING).path)
    print(f"측정 조건: {describe_metadata(meta)}", file=sys.stderr)

    results = []
    for name in names:
        print(f"  {name}", file=sys.stderr, flush=True)
        results.append(run_fixture(agent, name, model_name))

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"annex-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    report(results)
    print(f"\n실행 결과 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
