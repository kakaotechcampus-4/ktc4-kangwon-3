"""표시·광고 Tool을 평가셋 입력으로 실제 모델에 돌려 채점한다.

    cd ai
    python -m app.eval.advertising_runner --runs 3
    python -m app.eval.advertising_runner --only cosmetic_claim_led_mask --runs 5
    python -m app.eval.advertising_runner --rescore logs/eval/advertising-20261012-120000.json

입력 listing_text는 로컬 파일(tests/fixtures/_raw/advertising_dev_inputs.json, 저장소에 없음)이다.
평가셋에 적힌 지문과 다르면 실행하지 않는다. 추출을 부르지 않으므로 Tool 호출 비용만 든다.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from ..agents.base import AgentError
from ..clients.llm import MAX_RETRIES, TIMEOUT_SECONDS
from ..config import CHAT_MODELS, ModelProfile, load_settings, tool_profile
from ..prompts import PromptName, get_prompt
from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Product
from ..schemas.schemas import ToolName
from ..tools.advertising import AdvertisingReviewer, AdvertisingTool
from .advertising_scoring import CaseScore, load_eval_set, score_case
from .runner import _AI_ROOT, RESULT_DIR, describe_metadata, run_metadata

TRUTH_PATH = _AI_ROOT / "tests" / "eval_truth_advertising" / "dev.json"
_DECISION = ToolSelectionItem(tool_name=ToolName.LABEL_AD, selected=True, reason="평가 실행")


def build_model(spec: str):
    """'이름[#추론강도]'로 모델을 만든다. 서비스와 같은 base_url·키를 쓰고 허용 모델 설정은 바꾸지 않는다.

    추론 강도를 주면(예: openai/gpt-6-luna#low) 추론 모델로 보고 temperature를 보내지 않는다(0을 거부함).
    """
    from langchain_openai import ChatOpenAI

    name, _, effort = spec.partition("#")
    settings = load_settings()
    options = {"reasoning_effort": effort} if effort else {"temperature": 0}
    return name, ChatOpenAI(model=name, base_url=settings.base_url, api_key=settings.api_key, **options,
                            timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES, streaming=True, stream_usage=True)


def model_profile(spec: str | None) -> ModelProfile:
    """측정 조건으로 남길 모델 프로필.

    --model이 없으면 서비스와 같은 표시·광고 Tool 프로필(MODEL_PROFILE_OVERRIDES 반영),
    있으면 카탈로그 모델로 만든 즉석 프로필. 카탈로그에 없는 모델은 부르지 않는다(profiles.py 원칙).

    Args:
        spec: --model 값 '이름[#추론강도]'. 없으면 None.

    Returns:
        ModelProfile: 이번 측정의 모델 조건.

    Raises:
        SystemExit: 카탈로그에 없는 모델이거나 모델이 받지 않는 옵션 조합인 경우.
    """
    if spec is None:
        return tool_profile(ToolName.LABEL_AD)
    name, _, effort = spec.partition("#")
    if name not in CHAT_MODELS:
        raise SystemExit(f"카탈로그에 없는 모델입니다: {name} (허용: {', '.join(CHAT_MODELS)})")
    try:
        # build_model과 같은 옵션: 추론 강도를 주면 temperature를 보내지 않음
        return ModelProfile(f"--model {spec}", CHAT_MODELS[name],
                            temperature=None if effort else 0, reasoning_effort=effort or None)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


def run_case(tool: AdvertisingTool, product_id: str, lines: list[str], runs: int) -> list[dict]:
    """한 상품을 runs번 돌려 탐지 문구·버린 인용·오류를 남긴다."""
    outputs = []
    for _ in range(runs):
        started = time.perf_counter()
        try:
            result = tool.execute(Product(product_id=product_id, listing_text=lines), _DECISION)
        except AgentError as exc:
            outputs.append({"_failed": type(exc).__name__, "elapsed_s": round(time.perf_counter() - started, 1)})
            continue
        outputs.append({
            "detected": [phrase.model_dump(mode="json", include={"text", "risk_type", "risk_level"})
                         for phrase in result.result.detected_phrases],
            "dropped_quotes": result.query.get("dropped_quotes", []),
            # 틀린 이유를 보려고 모델의 줄별 검토도 남긴다.
            "line_checks": (result.raw_response or {}).get("line_checks", []),
            "elapsed_s": round(time.perf_counter() - started, 1),
        })
    return outputs


def report(truth: dict, results: dict[str, list[dict]]) -> None:
    """문구 단위 건수로 출력한다. 셋이 작아 비율은 쓰지 않는다."""
    cases = {case["product_id"]: case for case in truth["cases"]}
    totals = Counter()
    for product_id, outputs in results.items():
        case = cases[product_id]
        ok = [output for output in outputs if "_failed" not in output]
        scores: list[CaseScore] = [score_case(case, output["detected"]) for output in ok]
        totals["runs"] += len(outputs)
        totals["failed"] += len(outputs) - len(ok)
        totals["must_flag"] += len(case["must_flag"]) * len(ok)
        totals["hits"] += sum(len(s.hits) for s in scores)
        totals["false_positives"] += sum(len(s.false_positives) for s in scores)
        totals["unlabeled"] += sum(len(s.unlabeled) for s in scores)
        totals["type_mismatches"] += sum(len(s.type_mismatches) for s in scores)
        totals["dropped"] += sum(len(output["dropped_quotes"]) for output in ok)

        print(f"\n[{product_id}] {len(ok)}/{len(outputs)}회 성공")
        for item in case["must_flag"]:
            hit = sum(item["text"] in s.hits for s in scores)
            mismatch = sum(item["text"] in s.type_mismatches for s in scores)
            note = f" (유형 다름 {mismatch})" if mismatch else ""
            print(f"  {'O' if hit == len(ok) else ('-' if hit else 'X')} {hit}/{len(ok)} {item['text']}{note}")
        for label, key in (("오탐", "false_positives"), ("미분류", "unlabeled")):
            counted = Counter(text for s in scores for text in getattr(s, key))
            for text, count in counted.most_common():
                print(f"  {label} {count}/{len(ok)} {text}")
        dropped = Counter(text for output in ok for text in output["dropped_quotes"])
        for text, count in dropped.most_common():
            print(f"  버린 인용 {count}/{len(ok)} {text}")

    print(f"\n합계: 맞힘 {totals['hits']}/{totals['must_flag']}, 오탐 {totals['false_positives']}, "
          f"미분류 {totals['unlabeled']}, 유형 다름 {totals['type_mismatches']}, 버린 인용 {totals['dropped']}, "
          f"실패 {totals['failed']}/{totals['runs']}회")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="표시·광고 Tool 평가")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--truth", type=Path, default=TRUTH_PATH, help="평가셋 파일. 기본 dev.json")
    parser.add_argument("--only", action="append", default=[], help="이 product_id만 실행(여러 번 줄 수 있음)")
    parser.add_argument("--rescore", type=Path, help="저장한 결과를 현재 평가셋으로 다시 채점")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", help="카탈로그 모델 '이름[#추론강도]'. 없으면 표시·광고 Tool 프로필. 예: openai/gpt-6-luna#low")
    args = parser.parse_args()

    truth, inputs = load_eval_set(args.truth, _AI_ROOT)
    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        print(describe_metadata(saved["meta"]))
        report(truth, saved["results"])
        return 0

    # 모델을 만들기 전에 정함. 카탈로그 밖 모델·잘못된 옵션이면 호출 없이 멈춤
    profile = model_profile(args.model)
    if args.model:
        name, model = build_model(args.model)
        reviewer = AdvertisingReviewer(model, configured_model=name, usage_agent="advertising-eval")
    else:
        reviewer = AdvertisingReviewer(usage_agent="advertising-eval")
    tool = AdvertisingTool(reviewer=reviewer)
    targets = [case["product_id"] for case in truth["cases"] if not args.only or case["product_id"] in args.only]
    meta = run_metadata(runs=args.runs, profile=profile, prompt_path=get_prompt(PromptName.ADVERTISING).path)
    meta["inputs_sha256_12"] = truth["inputs_sha256_12"]
    meta["truth"] = args.truth.name
    print(describe_metadata(meta))

    results = {product_id: run_case(tool, product_id, inputs[product_id], args.runs) for product_id in targets}
    out = args.out or RESULT_DIR / f"advertising-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    report(truth, results)
    print(f"\n저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
