"""전기안전 Tool을 파이프라인 없이 실제 모델·법제처 API로 돌려 결과·토큰·시간을 확인한다.

    cd ai
    python -m app.eval.electrical_runner                          # .env 모델, 내장 상품 6개, 1회
    python -m app.eval.electrical_runner --only 전기포트 --runs 3
    python -m app.eval.electrical_runner --model openai/gpt-4.1-mini --model gpt-6-luna@LUNA --runs 3 \
        --price gpt-6-luna=1000,250,4000 --out logs/eval/electrical-compare.json
    python -m app.eval.electrical_runner --product product.json --json
    python -m app.eval.electrical_runner --eval tests/eval_truth_electrical/holdout.json --runs 3
    python -m app.eval.electrical_runner --eval tests/eval_truth_electrical/holdout.json --rescore logs/eval/<원자료>.json

--model 은 여러 번 줄 수 있다. 같은 상품을 모델마다 같은 횟수로 돌려 비교한다.
  - "이름"           : .env의 OPENAI_BASE_URL·OPENAI_API_KEY로 호출
  - "이름@접두어"    : .env(또는 환경변수)의 {접두어}_BASE_URL로 호출. 키는 {접두어}_API_KEY,
                       없으면 OPENAI_API_KEY (엘리스 ML API는 모델마다 엔드포인트만 다르다)
                       예: LUNA_BASE_URL=https://mlapi.run/<엔드포인트>/v1 → --model openai/gpt-6-luna@LUNA
  - 추론 모델은 temperature=0을 거부한다 → --default-temperature openai/gpt-6-luna
  - 추론 강도: "이름@접두어#low" (luna: none/low/medium/high/xhigh). 같은 모델을 강도별로 나란히 비교할 수 있다.
서비스 설정의 허용 모델(ALLOWED_MODELS)은 바꾸지 않는다. 이 스크립트에서만 모델을 직접 만든다.

--price 이름=입력,캐시입력,출력 (1M 토큰당 원). usage.PRICING_KRW에 없는 모델의 비용 추정에 쓴다.

비용이 든다. 조건이 부족한 상품은 법령 조회·두 번째 모델 호출 없이 끝난다.
결과는 POSSIBLY_REQUIRED·INSUFFICIENT_INFORMATION만 나온다. 확정 판단이 아니다.
"""

import argparse
import json
import os
import statistics
import sys
import warnings
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv

from .. import usage as usage_module
from ..clients.law import LawClient
from ..config import ENV_FILE, MAX_RETRIES, TIMEOUT_SECONDS
from ..schemas.agent import ToolSelectionItem
from ..schemas.product import Attribute, Product
from ..schemas.schemas import ToolName, ToolResult
from ..tools.electrical import ElectricalTool
from ..tools.electrical import tool as electrical_module
from ..tools.electrical.evidence import CachedEvidenceSource, LawApiEvidenceSource
from ..tools.electrical.search import LawApiItemSearch

# include_raw 응답을 직렬화할 때 LangChain 내부에서 나는 경고. 결과와 무관하고 출력만 가린다.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

# 결과 경로를 하나씩 보여주는 상품. 추출 에이전트가 만드는 Product 형식을 손으로 쓴 것이다.
SAMPLES = [
    # 기본 조건(종류·전원·전압)이 모두 있어 법령 후보 검토까지 간다.
    Product(
        product_id="demo-kettle",
        product_name="스테인리스 전기포트 1.7L",
        category="주방가전",
        electrical_powered=True,
        heating=True,
        listing_text=["스테인리스 전기포트 1.7L, AC 220V 60Hz 전용, 소비전력 1500W, 자동 전원 차단"],
    ),
    # 전압이 없어 "정격 전압 정보가 필요합니다"로 끝난다. 법령 조회 없음.
    Product(
        product_id="demo-usb-fan",
        product_name="휴대용 미니 선풍기",
        category="소형가전",
        electrical_powered=True,
        battery_included=True,
        listing_text=["USB 충전식 휴대용 미니 선풍기, 3단 풍속 조절"],
        attributes=[Attribute(name="배터리", value="2000mAh", source_text="내장 배터리 용량 2000mAh")],
    ),
    # 보조배터리. 전지 자체가 상품인 경우.
    Product(
        product_id="demo-power-bank",
        product_name="보조배터리 10000mAh",
        category="휴대폰 액세서리",
        electrical_powered=True,
        battery_is_the_product=True,
        listing_text=["리튬폴리머 보조배터리 10000mAh, 출력 DC 5V 2A, USB-C 입력"],
    ),
    # 휴대폰 충전기. 직류전원장치는 구매대행 특례 품목이지만 "휴대전화 전지 충전기는 제외"가 붙어 있다.
    Product(
        product_id="demo-phone-charger",
        product_name="20W USB-C 고속 충전기",
        category="휴대폰 액세서리",
        electrical_powered=True,
        listing_text=["스마트폰용 20W USB-C PD 고속 충전기, 입력 AC 100-240V, 출력 DC 5V/9V"],
    ),
    # 배터리로만 작동하는 무선 청소기. 공통 비고의 전지 전용 구조 제외를 확인한다.
    Product(
        product_id="demo-cordless-vacuum",
        product_name="무선 핸디 청소기",
        category="생활가전",
        electrical_powered=True,
        battery_included=True,
        listing_text=["무선 핸디 청소기, 내장 배터리로만 작동하며 전원 코드 없이 사용, 충전 거치대 포함"],
    ),
    # 전기를 쓰지 않는 상품. 조건이 없어 정보 부족으로 끝나야 한다(비대상으로 바꾸지 않음).
    Product(
        product_id="demo-spatula",
        product_name="실리콘 주걱",
        category="주방용품",
        electrical_powered=False,
        listing_text=["내열 실리콘 주걱, 식기세척기 사용 가능"],
    ),
]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} 를 {ENV_FILE} 또는 환경변수에 설정하세요.")
    return value


def build_model(spec: str, *, default_temperature: bool = False):
    """'이름[@접두어][#추론강도]'로 채팅 모델을 만든다. 서비스와 같은 호출 설정을 쓴다.

    추론 모델(gpt-6-luna 등)은 temperature=0을 거부하고 기본값(1)만 받는다.
    default_temperature=True면 temperature를 보내지 않는다.
    '#low'처럼 추론 강도(reasoning_effort)를 붙이면 그 값으로 호출한다(luna: none/low/medium/high/xhigh).
    """
    from langchain_openai import ChatOpenAI

    spec, _, effort = spec.partition("#")
    name, _, prefix = spec.partition("@")
    # 전체 서비스 설정(load_settings)은 이 실행에 필요 없는 키까지 요구하므로 필요한 값만 읽는다.
    base_url = _env(f"{prefix or 'OPENAI'}_BASE_URL")
    # 엘리스 ML API는 모델마다 엔드포인트가 다르고 키는 같다. 접두어 키가 없으면 기본 키를 쓴다.
    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip() if prefix else ""
    api_key = api_key or _env("OPENAI_API_KEY")
    options = {} if default_temperature else {"temperature": 0}
    if effort:
        options["reasoning_effort"] = effort
    return name, ChatOpenAI(
        model=name, base_url=base_url, api_key=api_key, **options,
        timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES, streaming=True, stream_usage=True,
    )


class UsageCapture:
    """Tool이 남기는 사용량 기록을 가로채 회차별로 모은다. 원래 로그(usage.jsonl)에도 그대로 쓴다.

    모델이 낸 원래 출력(버리기 전 조건·후보)도 함께 남겨, 무엇을 왜 버렸는지 --out 파일에서 볼 수 있게 한다.
    """

    def __init__(self, tool: ElectricalTool) -> None:
        self.calls: list[dict] = []
        self.outputs: dict[str, dict] = {}
        self._tool = tool
        self._original = electrical_module.record

    def __enter__(self):
        original_invoke = type(self._tool)._invoke

        def invoke(tool, model, schema, prompt_name, payload, product):
            parsed = original_invoke(tool, model, schema, prompt_name, payload, product)
            # 저장 키는 예전 원자료와 같게 "electrical_facts"·"electrical_review"로 둔다(--rescore 호환).
            self.outputs[f"electrical_{Path(prompt_name).stem}"] = parsed.model_dump(mode="json")
            return parsed

        self._tool._invoke = invoke.__get__(self._tool)
        def capture(agent, usage, **kw):
            self.calls.append({
                "agent": agent,
                "reported_model": usage.reported_model if usage else None,
                "input_tokens": usage.input_tokens if usage else None,
                "cached_tokens": usage.cached_tokens if usage else None,
                "output_tokens": usage.output_tokens if usage else None,
                "cost_krw": usage_module.estimate_krw(usage, kw.get("configured_model")) if usage else None,
                "latency_ms": kw.get("elapsed_ms"),
                "ok": kw.get("ok", True),
                "error_type": kw.get("error_type"),
            })
            self._original(agent, usage, **kw)

        electrical_module.record = capture
        return self

    def __exit__(self, *exc):
        electrical_module.record = self._original
        del self._tool._invoke


def run_once(tool: ElectricalTool, product: Product, decision: ToolSelectionItem) -> dict:
    with UsageCapture(tool) as captured:
        started = perf_counter()
        result: ToolResult | None = None
        error = error_detail = None
        try:
            result = tool.execute(product, decision)
        except Exception as exc:  # 비교 실행은 계속한다. 파이프라인에서는 Executor가 FAILED로 바꾼다.
            cause = exc.__cause__
            error = f"{type(exc).__name__}" + (f" ← {type(cause).__name__}" if cause else "")
            # 원인 메시지(게이트웨이 오류 문구 등)는 --out 파일에만 남긴다. 키는 메시지에 들어 있지 않다.
            error_detail = str(cause or exc)[:500]
        total_ms = round((perf_counter() - started) * 1000)
    model_ms = sum(c["latency_ms"] or 0 for c in captured.calls)
    return {
        "product_id": product.product_id,
        "status": result.status.value if result else "error",
        "error": error,
        "error_detail": error_detail,
        "total_ms": total_ms,
        "model_ms": model_ms,
        # 법령 조회와 코드 처리 시간(모델 호출 시간을 뺀 나머지).
        "other_ms": total_ms - model_ms,
        "calls": captured.calls,
        "query": result.query if result else None,
        "findings": [{"determination": f.determination.value, "subject": f.subject} for f in result.findings]
        if result else [],
        "missing_information": result.missing_information if result else [],
        # 모델 원래 출력. Tool이 원문 대조로 버린 항목도 여기에는 남아 있다.
        "model_outputs": captured.outputs,
        "result": result.model_dump(mode="json") if result else None,
    }


def describe_run(product: Product, model: str, index: int, run: dict) -> str:
    tokens = " / ".join(
        f"{c['agent'].removeprefix('electrical-')}: 입력 {c['input_tokens']}(캐시 {c['cached_tokens']}) "
        f"출력 {c['output_tokens']} {c['latency_ms']}ms" + ("" if c["ok"] else f" 실패({c['error_type']})")
        for c in run["calls"]
    ) or "모델 호출 없음"
    lines = [
        f"\n## {product.product_name or product.product_id} · {model} · {index + 1}회차",
        f"  상태 {run['status']}{' ' + run['error'] if run['error'] else ''}  "
        f"전체 {run['total_ms']}ms (모델 {run['model_ms']}ms, 법령·코드 {run['other_ms']}ms)",
        f"  토큰: {tokens}",
    ]
    if run["query"]:
        q = run["query"]
        lines.append(f"  버린 항목: 조건 {q.get('dropped_facts', 0)}, 선택 {q.get('dropped_candidates', 0)}"
                     f" · 저전압 {q.get('low_voltage')} · 전지 전용 {q.get('battery_only')}"
                     f" · 선택 행 {q.get('selected_items', [])} · 조회 후보 {len(q.get('candidate_items', []))}개"
                     f" · 구매대행 특례 {q.get('purchase_agent', {})}")
    for action in (run["result"] or {}).get("required_actions", []):
        lines.append(f"  ▶ {action}")
    for finding in run["findings"]:
        lines.append(f"  - [{finding['determination']}] {finding['subject']}")
    for item in run["missing_information"]:
        lines.append(f"  ? {item}")
    return "\n".join(lines)


def _stats(values: list[int]) -> str:
    if not values:
        return "-"
    return f"평균 {round(statistics.mean(values))} / 최대 {max(values)}"


def summarize(results: dict[str, list[dict]]) -> str:
    lines = ["\n# 모델별 요약 (상품 × 회차 전체)"]
    for model, runs in results.items():
        calls = [c for r in runs for c in r["calls"]]
        costs = [c["cost_krw"] for c in calls if c["cost_krw"] is not None]
        reported = sorted({c["reported_model"] for c in calls if c["reported_model"]})
        lines += [
            f"\n## {model}" + (f"  (게이트웨이 응답 모델: {', '.join(reported)})" if reported else ""),
            f"  실행 {len(runs)}회 · 오류 {sum(r['status'] == 'error' for r in runs)}회 · 모델 호출 {len(calls)}회"
            f" (실패 {sum(not c['ok'] for c in calls)})",
        ]
        for agent in ("electrical-facts", "electrical-review"):
            group = [c for c in calls if c["agent"] == agent and c["ok"]]
            if group:
                lines.append(
                    f"  {agent.removeprefix('electrical-'):7s}: 입력 {_stats([c['input_tokens'] or 0 for c in group])}"
                    f" · 캐시 {_stats([c['cached_tokens'] or 0 for c in group])}"
                    f" · 출력 {_stats([c['output_tokens'] or 0 for c in group])}"
                    f" · 지연 {_stats([c['latency_ms'] or 0 for c in group])}ms"
                )
        lines.append(f"  상품 1회 전체 시간 {_stats([r['total_ms'] for r in runs])}ms"
                     f" · 버린 조건 {sum((r['query'] or {}).get('dropped_facts', 0) for r in runs)}"
                     f" · 버린 후보 {sum((r['query'] or {}).get('dropped_candidates', 0) for r in runs)}")
        lines.append(f"  예상 비용 {round(sum(costs), 2)}원" if costs and len(costs) == len(calls)
                     else "  예상 비용: 단가 미등록(--price로 지정)")
        # 같은 상품을 여러 번 돌렸을 때 후보가 흔들리는지 본다(규칙으로 올릴 후보 찾기).
        for product_id in dict.fromkeys(r["product_id"] for r in runs):
            outcomes = [" | ".join(f"{f['determination']}:{f['subject']}" for f in r["findings"]) or r["status"]
                        for r in runs if r["product_id"] == product_id]
            mark = "같음" if len(set(outcomes)) == 1 else f"흔들림 {len(set(outcomes))}종"
            lines.append(f"  [{mark}] {product_id}: " + "  ⟂  ".join(dict.fromkeys(outcomes)))
    return "\n".join(lines)


def _register_prices(specs: list[str]) -> None:
    for spec in specs:
        name, _, numbers = spec.partition("=")
        values = [float(x) for x in numbers.split(",")]
        if len(values) != 3:
            raise SystemExit(f"--price 형식: 이름=입력,캐시입력,출력  ({spec})")
        usage_module.PRICING_KRW[name] = dict(zip(("input", "cached_input", "output"), values))


def score_eval(results: dict[str, list[dict]], cases: dict[str, dict]) -> str:
    """평가셋 채점. 품목 행 선택 정확도이며, 법적 판정이나 판매 안내의 정확도가 아니다.

    - 실행 실패(예외)는 따로 세고 정답에 넣지 않는다.
    - 조회 recall@k와 정답률은 정답 행이 있는 사례만으로 낸다.
    - 정답 행이 없는 사례(본체 행을 고르지 않아야 하는 경우)는 별도 지표로 낸다.
    """
    lines = ["\n# 평가셋 채점 (품목 행 선택 정확도. 법적 판정·판매 안내의 정확도가 아니다)"]
    for model, runs in results.items():
        stats = dict(runs=0, errors=0, with_rows=0, retrieval=0, correct=0, wrong=0,
                     no_rows=0, no_rows_correct=0, split_ok=0, split_total=0)
        per_case: dict[str, list[str]] = {}
        for run in runs:
            case = cases.get(run["product_id"])
            if case is None:
                continue
            stats["runs"] += 1
            if run["status"] == "error":
                stats["errors"] += 1
                per_case.setdefault(run["product_id"], []).append("E")
                continue
            q = run["query"] or {}
            selected = set(q.get("selected_items") or [])
            expected, acceptable = set(case["expected_rows"]), set(case.get("acceptable_rows", []))
            wrong = selected - expected - acceptable
            if expected:
                stats["with_rows"] += 1
                stats["retrieval"] += bool(set(q.get("candidate_items") or []) & expected)
                ok = bool(selected & expected) and not wrong
                stats["correct"] += ok
            else:
                stats["no_rows"] += 1
                ok = not wrong
                stats["no_rows_correct"] += ok
            stats["wrong"] += bool(wrong)
            mark = "O" if ok else ("x" if wrong else ".")
            per_case.setdefault(run["product_id"], []).append(mark + (f"{sorted(wrong)}" if wrong else ""))
            # 전류 종류와 전압이 한 표현에 함께 있는 원문에서 둘을 나눠 뽑았는가(프롬프트 예시 없이)
            facts = (run["model_outputs"].get("electrical_facts") or {}).get("facts", [])
            if any(word in " ".join(case["product"].get("listing_text", [])) for word in ("AC ", "DC ")):
                stats["split_total"] += 1
                stats["split_ok"] += {"power_source", "rated_voltage"} <= {f["field"] for f in facts}
        if not stats["runs"]:
            continue
        s = stats
        lines += [
            f"\n## {model}",
            f"  실행 {s['runs']}회 · 실행 실패 {s['errors']}회 (실패는 정답에서 제외)",
            f"  정답 행이 있는 사례 {s['with_rows']}회: 조회 recall@k {s['retrieval']}/{s['with_rows']}"
            f" · 정답 행 선택(오답 행 없이) {s['correct']}/{s['with_rows']}",
            f"  정답 행이 없는 사례 {s['no_rows']}회: 본체 행을 고르지 않음 {s['no_rows_correct']}/{s['no_rows']}",
            f"  오답 행 포함 {s['wrong']}회 · 전원/전압 분리 {s['split_ok']}/{s['split_total']}",
        ]
        lines += [f"  {pid:20s} {' '.join(marks)}" for pid, marks in per_case.items()]
    lines.append("  (O 정답 · . 정답 행을 고르지 못함(정보 부족 등) · x 오답 행 포함 · E 실행 실패)")
    return "\n".join(lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="전기안전 Tool 단독 실행·모델 비교")
    parser.add_argument("--eval", type=Path, help="평가셋 JSON(tests/eval_truth_electrical/holdout.json). 채점까지 한다")
    parser.add_argument("--rescore", type=Path, help="저장한 --out 원자료를 --eval 평가셋으로 다시 채점만 한다(API 호출 없음)")
    parser.add_argument("--model", action="append", default=[], help="모델 이름 또는 이름@접두어 (여러 번 가능)")
    parser.add_argument("--runs", type=int, default=1, help="상품·모델마다 반복 횟수 (기본 1)")
    parser.add_argument("--product", type=Path, help="Product JSON 파일 (없으면 내장 상품)")
    parser.add_argument("--only", help="내장 상품 중 이름에 이 문자열이 들어간 것만 실행")
    parser.add_argument("--price", action="append", default=[], help="이름=입력,캐시입력,출력 (1M 토큰당 원)")
    parser.add_argument("--default-temperature", action="append", default=[], metavar="이름",
                        help="temperature=0을 거부하는 추론 모델. 기본값(1)으로 호출한다 (여러 번 가능)")
    parser.add_argument("--json", action="store_true", help="회차별 요약 대신 ToolResult 전체를 출력")
    parser.add_argument("--out", type=Path, help="회차별 원자료(토큰·시간·결과)를 JSON으로 저장")
    args = parser.parse_args()

    load_dotenv(ENV_FILE, override=False, encoding="utf-8-sig")
    _register_prices(args.price)
    cases: dict[str, dict] = {}
    if args.eval:
        cases = {case["product"]["product_id"]: case
                 for case in json.loads(args.eval.read_text(encoding="utf-8"))["cases"]}
        products = [Product.model_validate(case["product"]) for case in cases.values()]
        if args.rescore:
            print(score_eval(json.loads(args.rescore.read_text(encoding="utf-8")), cases))
            return 0
    elif args.product:
        products = [Product.model_validate_json(args.product.read_text(encoding="utf-8"))]
    else:
        products = [p for p in SAMPLES if not args.only or args.only in (p.product_name or "")]
    if not products or args.runs < 1:
        parser.error("실행할 상품이 없거나 --runs가 1보다 작습니다.")

    specs = args.model or [_env("OPENAI_MODEL")]
    decision = ToolSelectionItem(tool_name=ToolName.ELECTRICAL, selected=True, reason="단독 실행 확인")
    results: dict[str, list[dict]] = {}
    law_client = LawClient(oc=_env("LAW_GO_KR_OC"))
    try:
        # 서버에서처럼 품목표는 한 번 받아 캐시한다. 최초 로드 시간은 따로 보여 주고 상품별 시간에서 뺀다.
        item_search = LawApiItemSearch(CachedEvidenceSource(LawApiEvidenceSource(law_client)))
        started = perf_counter()
        item_search.load()
        print(f"법령 품목표 로드(최초 1회, 이후 캐시): {round((perf_counter() - started) * 1000)}ms", flush=True)
        for spec in specs:
            name, model = build_model(spec, default_temperature=spec.partition("#")[0].partition("@")[0]
                                      in args.default_temperature)
            tool = ElectricalTool(model, configured_model=name, item_search=item_search)
            # 같은 모델을 추론 강도만 바꿔 비교할 수 있게 결과는 '이름#강도'로 나눈다.
            label = name + (f"#{spec.partition('#')[2]}" if "#" in spec else "")
            name = label
            results[name] = []
            for product in products:
                for index in range(args.runs):
                    run = run_once(tool, product, decision)
                    results[name].append(run)
                    if args.json:
                        print(json.dumps(run["result"] or run, ensure_ascii=False, indent=2))
                    else:
                        print(describe_run(product, name, index, run), flush=True)
    finally:
        law_client.close()

    print(summarize(results))
    if cases:
        print(score_eval(results, cases))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n원자료 저장: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
