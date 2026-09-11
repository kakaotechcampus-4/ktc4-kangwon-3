"""모델 호출의 토큰 사용량을 JSONL로 남긴다.

팀 크레딧이 공용이라 어느 에이전트가 얼마나 쓰는지 보이지 않으면 관리할 수 없다.
호출 1건이 한 줄이고, 상품 텍스트는 남기지 않는다(식별자와 숫자만).

총계 보기:

    python -m app.usage
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# 테스트에서 monkeypatch로 바꿔 쓰므로 모듈 전역으로 둔다.
USAGE_LOG = Path(__file__).resolve().parent.parent / "logs" / "usage.jsonl"

# 카테캠 엘리스 ML API Serverless 단가(1M 토큰당 KRW).
# 모델 라이브러리 화면에 표시된 2026-09-07 기준 금액이다.
PRICING_KRW = {
    "openai/gpt-4.1-mini": {"input": 609.0, "cached_input": 152.0, "output": 2436.0},
}


@dataclass(frozen=True)
class CallUsage:
    """호출 1건의 토큰 사용량. cached_tokens는 input_tokens에 포함된 값이다."""

    reported_model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int

    @property
    def uncached_input(self) -> int:
        # 캐시 적중분은 단가가 낮아 따로 계산한다. 음수가 되지 않게 막는다.
        return max(self.input_tokens - self.cached_tokens, 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def from_handler(handler) -> CallUsage | None:
    """UsageMetadataCallbackHandler에서 사용량을 뽑는다.

    실제 모델 호출이 없었으면(테스트 스텁 등) None을 돌려준다.
    핸들러는 모델 이름을 키로 집계하므로 호출마다 새 핸들러를 쓰면 항목이 하나다.
    """
    metadata = getattr(handler, "usage_metadata", None) or {}
    if not metadata:
        return None
    models = ", ".join(sorted(metadata))
    total_in = total_cached = total_out = 0
    for entry in metadata.values():
        total_in += entry.get("input_tokens", 0) or 0
        total_out += entry.get("output_tokens", 0) or 0
        # 프록시가 캐시 적중분을 알려준다. 없을 수도 있어 기본값을 둔다.
        total_cached += (entry.get("input_token_details") or {}).get("cache_read", 0) or 0
    return CallUsage(models, total_in, total_cached, total_out)


def estimate_krw(usage: CallUsage, configured_model: str | None) -> float | None:
    """카테캠 ML API 단가로 예상 비용을 계산한다. 단가를 모르면 None이다."""
    price = PRICING_KRW.get(configured_model or "")
    if price is None:
        return None
    krw = (
        usage.uncached_input * price["input"]
        + usage.cached_tokens * price["cached_input"]
        + usage.output_tokens * price["output"]
    ) / 1_000_000
    return round(krw, 4)


def record(
    agent: str,
    usage: CallUsage | None,
    *,
    configured_model: str | None = None,
    subject_id: str | None = None,
    ok: bool = True,
    elapsed_ms: int | None = None,
    error_type: str | None = None,
) -> None:
    """호출 1건을 기록한다. 로깅 실패가 검증을 막지 않도록 어떤 예외도 밖으로 내지 않는다."""
    try:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "agent": agent,
            "configured_model": configured_model,
            # 프록시가 실제로 돌린 모델. 요청한 모델과 다른지 확인할 수 있다.
            "reported_model": usage.reported_model if usage else None,
            "input_tokens": usage.input_tokens if usage else None,
            "cached_input_tokens": usage.cached_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
            "estimated_cost_krw": estimate_krw(usage, configured_model) if usage else None,
            "subject_id": subject_id,
            "success": ok,
            "latency_ms": elapsed_ms,
            # 예외 메시지는 응답 내용이나 민감 정보를 포함할 수 있어 타입만 남긴다.
            "error_type": error_type,
        }
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # 사용량 기록은 부가 기능이다. 파일 오류든 직렬화 오류든 호출 결과를 버리지 않는다.
        pass


def summarize(path: Path | None = None) -> dict:
    """기록된 호출을 합산한다. 깨진 줄은 건너뛴다."""
    target = path or USAGE_LOG
    totals = {
        "calls": 0,
        "failed": 0,
        "input": 0,
        "cached": 0,
        "output": 0,
        "est_krw": 0.0,
        "by_agent": {},
    }
    if not target.exists():
        return totals
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        totals["calls"] += 1
        # 필드명을 풀어 쓰기 전의 기존 JSONL도 계속 집계한다.
        if not row.get("success", row.get("ok", True)):
            totals["failed"] += 1
        totals["input"] += row.get("input_tokens", row.get("input")) or 0
        totals["cached"] += row.get("cached_input_tokens", row.get("cached")) or 0
        totals["output"] += row.get("output_tokens", row.get("output")) or 0
        krw = row.get("estimated_cost_krw", row.get("est_krw")) or 0
        totals["est_krw"] += krw
        agent = row.get("agent") or "unknown"
        bucket = totals["by_agent"].setdefault(agent, {"calls": 0, "est_krw": 0.0})
        bucket["calls"] += 1
        bucket["est_krw"] = round(bucket["est_krw"] + krw, 4)
    totals["est_krw"] = round(totals["est_krw"], 2)
    return totals


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    totals = summarize()
    if totals["calls"] == 0:
        print(f"기록이 없습니다: {USAGE_LOG}")
        return 0
    cached_ratio = totals["cached"] / totals["input"] * 100 if totals["input"] else 0
    print(f"기록 파일: {USAGE_LOG}")
    print(f"호출 {totals['calls']}회 (실패 {totals['failed']}회)")
    print(f"입력 {totals['input']:,} 토큰 (캐시 {totals['cached']:,} = {cached_ratio:.0f}%)")
    print(f"출력 {totals['output']:,} 토큰")
    print(f"예상 비용 {totals['est_krw']:,.2f}원  <- 카테캠 ML API 표시 단가 기준입니다")
    for agent, bucket in sorted(totals["by_agent"].items()):
        print(f"  {agent}: {bucket['calls']}회, {bucket['est_krw']:,.2f}원")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
