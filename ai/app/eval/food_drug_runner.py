"""식약 Tool을 파이프라인 없이 실제 모델·법제처 API로 돌려 결과·토큰·시간을 확인한다.

    cd ai
    python -m app.eval.food_drug_runner                                  # Tool 프로필 모델, 내장 상품, 1회
    python -m app.eval.food_drug_runner --only 체온계 --runs 3
    python -m app.eval.food_drug_runner --product product.json --json
    python -m app.eval.food_drug_runner --eval tests/eval_truth_food_drug/holdout.json --runs 3 --out logs/eval/food-drug.json

--model 형식은 electrical_runner와 같다("이름", "이름@접두어", "이름@접두어#추론강도").
--eval 평가셋은 상품마다 예상 분류(food_contact / food / cosmetic / functional / device, 비면 해당 없음)와, 의료기기면 예상 품목 분류번호 목록을 둔다.
  - 분류: 결과의 regulatory_categories가 예상과 같은지("none"은 둘 다 없음).
  - 품목: 의료기기 예상 상품에서 선택한 품목 중 하나가 예상 품목 목록에 있는지.
실행 실패는 따로 세고 정답에서 뺀다. 비용이 든다. 결과는 POSSIBLY_REQUIRED·INSUFFICIENT_INFORMATION만 나온다.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from .. import usage as usage_module
from ..config import ENV_FILE, MODEL_PROFILES, TOOL_PROFILES
from ..config.settings import OVERRIDES_ENV, ConfigError, parse_profile_overrides
from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Product
from ..schemas.schemas import ToolName
from ..tools.common.law import KST, CachedLoader, LawApiClients
from ..tools.food_drug import FoodDrugTool
from ..tools.food_drug.evidence import load_food_drug_evidence
from .electrical_runner import _env, build_model

SAMPLES = [
    Product(product_id="demo-spatula", product_name="실리콘 주걱", category="주방용품",
            listing_text=["내열 실리콘 주걱, 볶음·부침 요리할 때 쓰는 조리도구"]),
    Product(product_id="demo-tumbler", product_name="스테인리스 텀블러", category="주방용품",
            listing_text=["스테인리스 이중 진공 텀블러 500ml, 커피·음료 보온보냉"]),
    Product(product_id="demo-thermometer", product_name="비접촉 적외선 체온계", category="건강",
            listing_text=["비접촉 적외선 체온계, 이마에 대면 1초 만에 체온 측정"]),
    Product(product_id="demo-tens", product_name="저주파 마사지기", category="건강",
            listing_text=["저주파 마사지기, 근육통 완화, 패드 4개 포함, 충전식"]),
    Product(product_id="demo-bracelet", product_name="게르마늄 팔찌", category="패션잡화",
            listing_text=["게르마늄 팔찌, 혈액순환 개선과 피로 회복에 도움"]),
    Product(product_id="demo-tshirt", product_name="면 티셔츠", category="의류", listing_text=["면 100% 반팔 티셔츠"]),
    Product(product_id="demo-collagen", product_name="콜라겐 젤리 스틱", category="건강식품",
            listing_text=["저분자 콜라겐 젤리 스틱 30포, 하루 1포 섭취, 피부 보습에 도움"]),
    Product(product_id="demo-cream", product_name="미백 크림", category="화장품",
            listing_text=["미백 기능성 크림 50ml, 얼굴에 바르는 크림, 전성분: 정제수, 글리세린, 나이아신아마이드"]),
]


class UsageCapture:
    """Tool이 남기는 사용량 기록을 가로채 회차별로 모은다. 원래 로그에도 그대로 쓴다."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._original = usage_module.record

    def __enter__(self):
        def capture(agent, usage, **kw):
            self.calls.append({
                "agent": agent, "input_tokens": usage.input_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
                "cost_krw": usage_module.estimate_krw(usage, kw.get("configured_model")) if usage else None,
                "latency_ms": kw.get("elapsed_ms"), "ok": kw.get("ok", True),
            })
            self._original(agent, usage, **kw)

        usage_module.record = capture
        return self

    def __exit__(self, *exc):
        usage_module.record = self._original


def run_once(tool: FoodDrugTool, product: Product) -> dict:
    decision = ToolSelectionItem(tool_name=ToolName.FOOD_DRUG, selected=True, reason="단독 실행 확인")
    with UsageCapture() as captured:
        started = perf_counter()
        result = error = None
        try:
            result = tool.execute(product, decision)
        except Exception as exc:  # 비교 실행은 계속한다. 파이프라인에서는 Executor가 FAILED로 바꾼다.
            cause = exc.__cause__
            error = f"{type(exc).__name__}" + (f" ← {type(cause).__name__}: {str(cause)[:200]}" if cause else "")
        total_ms = round((perf_counter() - started) * 1000)
    return {
        "status": "error" if result is None else "success", "error": error, "total_ms": total_ms,
        "calls": captured.calls, "query": result.query if result else None,
        "categories": result.result.regulatory_categories if result else [],
        "findings": [f"[{f.determination.value}] {f.subject}" for f in result.findings] if result else [],
        "actions": result.required_actions if result else [],
        "missing": result.missing_information if result else [],
    }


def describe(product: Product, model: str, index: int, run: dict) -> str:
    query = run["query"] or {}
    lines = [f"\n## {product.product_name} · {model} · {index}회차",
             f"  상태 {run['status']}  전체 {run['total_ms']}ms" + (f"  오류 {run['error']}" if run["error"] else ""),
             f"  분류 {run['categories']} · 효능 문구 {query.get('health_claims')} · 품목 후보 "
             f"{len(query.get('candidate_items', []))}개 · 선택 {query.get('selected_items')}"]
    lines += [f"  - {text}" for text in run["findings"]]
    lines += [f"  ▶ {text}" for text in run["actions"]]
    lines += [f"  ? {text}" for text in run["missing"]]
    lines.append("  토큰: " + " / ".join(f"{c['agent']} 입력 {c['input_tokens']} 출력 {c['output_tokens']} "
                                         f"{c['latency_ms']}ms" for c in run["calls"]))
    return "\n".join(lines)


_CATEGORY = {"food_contact": "식품용 기구·용기", "food": "식품·건강기능식품", "cosmetic": "화장품",
             "functional": "기능성화장품", "device": "의료기기"}


def score(results: dict[str, list[tuple[str, dict]]], cases: dict[str, dict]) -> str:
    lines = ["\n# 평가 (사람 검토 전 정답)"]
    for model, runs in results.items():
        done = [(pid, run) for pid, run in runs if run["status"] == "success"]
        category_hits, item_hits, item_total = 0, 0, 0
        rows = []
        for pid, run in done:
            expected = cases[pid]
            want = sorted(_CATEGORY[name] for name in expected["categories"])
            category_ok = sorted(run["categories"]) == want
            category_hits += category_ok
            item_ok = None
            if expected.get("device_items"):
                item_total += 1
                picked = (run["query"] or {}).get("selected_items") or []
                item_ok = any(item in expected["device_items"] for item in picked)
                item_hits += item_ok
            rows.append(f"  {'O' if category_ok else 'X'}{'' if item_ok is None else ('O' if item_ok else 'X')} "
                        f"{pid}: 예상 {want} · 결과 {run['categories']}"
                        + ("" if item_ok is None else f" · 품목 {(run['query'] or {}).get('selected_items')}"))
        lines.append(f"## {model}: 실행 {len(runs)} · 실패 {len(runs) - len(done)} · 분류 정답 {category_hits}/{len(done)}"
                     f" · 의료기기 품목 정답 {item_hits}/{item_total}")
        lines += rows
    return "\n".join(lines)


def default_spec(default_temperature: list[str]) -> str:
    """--model이 없을 때 이 Tool의 프로필(MODEL_PROFILE_OVERRIDES의 tool.{이름} 또는 기본값)을 '이름[#추론강도]'로.

    electrical_runner.default_spec과 같다. 프로필에 temperature가 없으면 default_temperature에 모델 이름을 넣는다.
    """
    try:
        overrides = parse_profile_overrides(os.environ.get(OVERRIDES_ENV, ""))
    except ConfigError as exc:
        raise SystemExit(str(exc)) from None
    name = overrides.get(("tool", ToolName.FOOD_DRUG), TOOL_PROFILES[ToolName.FOOD_DRUG])
    if name not in MODEL_PROFILES:
        raise SystemExit(f"{OVERRIDES_ENV}의 tool.{ToolName.FOOD_DRUG}={name!r}는 없는 프로필입니다 "
                         f"(허용: {', '.join(MODEL_PROFILES)}).")
    profile = MODEL_PROFILES[name]
    if profile.temperature is None:
        default_temperature.append(profile.model.id)
    return profile.model.id + (f"#{profile.reasoning_effort}" if profile.reasoning_effort else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", help="모델(여러 번 가능). 없으면 이 Tool의 모델 프로필")
    parser.add_argument("--default-temperature", action="append", default=[], help="temperature를 보내지 않을 모델")
    parser.add_argument("--only", help="상품명에 이 글자가 들어간 내장 상품만")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--product", type=Path, help="Product JSON 파일")
    parser.add_argument("--eval", type=Path, help="평가셋 JSON(tests/eval_truth_food_drug/holdout.json)")
    parser.add_argument("--out", type=Path, help="회차별 원자료를 JSON으로 저장")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = parser.parse_args()
    load_dotenv(ENV_FILE)

    cases: dict[str, dict] = {}
    if args.eval:
        truth = json.loads(args.eval.read_text(encoding="utf-8"))
        products = [Product(**case["product"]) for case in truth["cases"]]
        cases = {case["product"]["product_id"]: case for case in truth["cases"]}
    elif args.product:
        products = [Product(**json.loads(args.product.read_text(encoding="utf-8")))]
    else:
        products = [p for p in SAMPLES if not args.only or args.only in (p.product_name or "")]
    if not products or args.runs < 1:
        parser.error("실행할 상품이 없거나 --runs가 1보다 작습니다.")

    law_client = LawApiClients.from_oc(_env("LAW_GO_KR_OC"))
    evidence = CachedLoader(lambda as_of: load_food_drug_evidence(law_client, as_of))
    today = datetime.now(KST).date()
    results: dict[str, list[tuple[str, dict]]] = {}
    try:
        started = perf_counter()
        evidence.load(today)
        print(f"식약 근거 로드(최초 1회, 이후 캐시): {round((perf_counter() - started) * 1000)}ms", flush=True)
        for spec in args.model or [default_spec(args.default_temperature)]:
            name, model = build_model(spec, default_temperature=spec in args.default_temperature)
            tool = FoodDrugTool(model, evidence=lambda: evidence.load(today), configured_model=name)
            for product in products:
                for index in range(1, args.runs + 1):
                    run = run_once(tool, product)
                    results.setdefault(spec, []).append((product.product_id, run))
                    if not args.json:
                        print(describe(product, spec, index, run), flush=True)
    finally:
        law_client.close()
    if args.json:
        print(json.dumps({model: [run for _, run in runs] for model, runs in results.items()},
                         ensure_ascii=False, indent=2))
    if cases:
        print(score(results, cases))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({m: [{"product_id": pid, **run} for pid, run in runs]
                                        for m, runs in results.items()}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
