"""통관 Tool을 파이프라인 없이 실제 모델·법제처·CLIP(·세관장확인 GW)으로 돌려 결과·토큰·시간을 확인한다.

    cd ai
    python -m app.eval.customs_runner                                   # Tool 프로필 모델, 내장 상품, 1회
    python -m app.eval.customs_runner --only 전기주전자 --runs 3
    python -m app.eval.customs_runner --product product.json --json
    python -m app.eval.customs_runner --eval tests/eval_truth_customs/holdout.json --runs 3 --out logs/eval/customs.json

--model 형식은 electrical_runner와 같다("이름", "이름@접두어", "이름@접두어#추론강도").
세관장확인 GW는 .env의 DATA_GO_KR_KEY가 있을 때만 조회한다. 없으면 HS 후보까지만 확인하고 요건은 "조회하지 못함"이 된다.

--eval 평가셋은 상품마다 예상 HS 앞자리(4·6자리)를 둔다. 선택한 HS 후보 중 하나가 그 앞자리로 시작하면 맞은 것이다.
조회 recall은 선택 전 후보 사례의 HS 중 하나라도 맞는지다. 실행 실패는 따로 세고 정답에서 뺀다.
비용이 든다. 결과는 POSSIBLY_REQUIRED·INSUFFICIENT_INFORMATION만 나온다. 확정 판단이 아니다.
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
from ..tools.customs import CustomsTool
from ..tools.customs.evidence import load_customs_evidence
from ..tools.customs.search import ClipCaseSearch, GwRequirementLookup
from .electrical_runner import _env, build_model

SAMPLES = [
    Product(product_id="demo-kettle", product_name="스테인리스 무선 전기주전자 1.7L", category="주방가전",
            listing_text=["스테인리스 무선 전기주전자 1.7L, AC 220V, 전기로 물을 끓이는 주방 가전"]),
    Product(product_id="demo-spatula", product_name="실리콘 주걱", category="주방용품",
            listing_text=["내열 실리콘 주걱, 손잡이 원목, 조리용"]),
    Product(product_id="demo-earphone", product_name="블루투스 무선 이어폰", category="음향기기",
            listing_text=["블루투스 5.3 무선 이어폰, 충전 케이스 포함"]),
    Product(product_id="demo-tumbler", product_name="스테인리스 진공 텀블러 500ml", category="주방용품",
            listing_text=["스테인리스 이중 진공 단열 텀블러 500ml, 보온보냉"]),
    Product(product_id="demo-block", product_name="조립 블록 장난감 500pcs", category="완구",
            listing_text=["플라스틱 조립 블록 장난감 500pcs, 만 6세 이상"]),
    Product(product_id="demo-tshirt", product_name="면 반팔 티셔츠", category="의류",
            listing_text=["면 100% 반팔 티셔츠, 니트(편직) 원단"]),
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


def run_once(tool: CustomsTool, product: Product) -> dict:
    decision = ToolSelectionItem(tool_name=ToolName.CUSTOMS, selected=True, reason="단독 실행 확인")
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
        "hs_candidates": result.result.hs_code_candidates if result else [],
        "findings": [f"[{f.determination.value}] {f.subject}" for f in result.findings] if result else [],
        "actions": result.required_actions if result else [],
        "missing": result.missing_information if result else [],
    }


def describe(product: Product, model: str, index: int, run: dict) -> str:
    query = run["query"] or {}
    lines = [f"\n## {product.product_name} · {model} · {index}회차",
             f"  상태 {run['status']}  전체 {run['total_ms']}ms"
             + (f"  오류 {run['error']}" if run["error"] else ""),
             f"  검색어 {query.get('search_terms')} (실패 {query.get('failed_terms')}) · 후보 사례 "
             f"{len(query.get('candidate_cases', []))}개 · 선택 {query.get('selected_cases')}",
             f"  HS 후보 {run['hs_candidates']} · 요건 {query.get('requirements')}"]
    lines += [f"  - {text}" for text in run["findings"]]
    lines += [f"  ▶ {text}" for text in run["actions"]]
    lines += [f"  ? {text}" for text in run["missing"]]
    tokens = [f"{c['agent']} 입력 {c['input_tokens']} 출력 {c['output_tokens']} {c['latency_ms']}ms"
              for c in run["calls"]]
    lines.append("  토큰: " + " / ".join(tokens))
    return "\n".join(lines)


def _digits(text: str) -> str:
    return "".join(char for char in text if char.isdigit())


def score(results: dict[str, list[tuple[str, dict]]], cases: dict[str, list[str]]) -> str:
    """선택 HS 정답률과 후보 사례 recall. 실행 실패는 정답에서 뺀다."""
    lines = ["\n# 평가 (예상 HS 앞자리 기준, 사람 검토 전 정답)"]
    for model, runs in results.items():
        done = [(pid, run) for pid, run in runs if run["status"] == "success"]
        hit = sum(any(_digits(hs).startswith(_digits(prefix)) for hs in run["hs_candidates"] for prefix in cases[pid])
                  for pid, run in done)
        lines.append(f"## {model}: 실행 {len(runs)} · 실패 {len(runs) - len(done)} · HS 정답 {hit}/{len(done)}")
        for pid, run in done:
            got = run["hs_candidates"]
            ok = any(_digits(hs).startswith(_digits(prefix)) for hs in got for prefix in cases[pid])
            lines.append(f"  {'O' if ok else 'X'} {pid}: 예상 {cases[pid]} · 후보 {got}")
    return "\n".join(lines)


def default_spec(default_temperature: list[str]) -> str:
    """--model이 없을 때 이 Tool의 프로필(MODEL_PROFILE_OVERRIDES의 tool.{이름} 또는 기본값)을 '이름[#추론강도]'로.

    electrical_runner.default_spec과 같다. 프로필에 temperature가 없으면 default_temperature에 모델 이름을 넣는다.
    """
    try:
        overrides = parse_profile_overrides(os.environ.get(OVERRIDES_ENV, ""))
    except ConfigError as exc:
        raise SystemExit(str(exc)) from None
    name = overrides.get(("tool", ToolName.CUSTOMS), TOOL_PROFILES[ToolName.CUSTOMS])
    if name not in MODEL_PROFILES:
        raise SystemExit(f"{OVERRIDES_ENV}의 tool.{ToolName.CUSTOMS}={name!r}는 없는 프로필입니다 "
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
    parser.add_argument("--eval", type=Path, help="평가셋 JSON(tests/eval_truth_customs/holdout.json)")
    parser.add_argument("--out", type=Path, help="회차별 원자료를 JSON으로 저장")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = parser.parse_args()
    load_dotenv(ENV_FILE)

    expected: dict[str, list[str]] = {}
    if args.eval:
        truth = json.loads(args.eval.read_text(encoding="utf-8"))
        products = [Product(**case["product"]) for case in truth["cases"]]
        expected = {case["product"]["product_id"]: case["expected_hs"] for case in truth["cases"]}
    elif args.product:
        products = [Product(**json.loads(args.product.read_text(encoding="utf-8")))]
    else:
        products = [p for p in SAMPLES if not args.only or args.only in (p.product_name or "")]
    if not products or args.runs < 1:
        parser.error("실행할 상품이 없거나 --runs가 1보다 작습니다.")

    law_client = LawApiClients.from_oc(_env("LAW_GO_KR_OC"))
    evidence = CachedLoader(lambda as_of: load_customs_evidence(law_client, as_of))
    today = datetime.now(KST).date()
    requirements = GwRequirementLookup(os.environ.get("DATA_GO_KR_KEY", "").strip() or None)
    results: dict[str, list[tuple[str, dict]]] = {}
    try:
        started = perf_counter()
        evidence.load(today)
        print(f"통관 근거 로드(최초 1회, 이후 캐시): {round((perf_counter() - started) * 1000)}ms", flush=True)
        for spec in args.model or [default_spec(args.default_temperature)]:
            name, model = build_model(spec, default_temperature=spec in args.default_temperature)
            tool = CustomsTool(model, case_search=ClipCaseSearch(), requirements=requirements,
                               evidence=lambda: evidence.load(today), configured_model=name)
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
    if expected:
        print(score(results, expected))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({m: [{"product_id": pid, **run} for pid, run in runs]
                                        for m, runs in results.items()}, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
