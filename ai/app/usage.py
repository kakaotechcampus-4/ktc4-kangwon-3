"""모델 호출의 토큰 사용량을 JSONL로 남긴다.

팀 크레딧이 공용이라 어느 에이전트가 얼마나 쓰는지 보이지 않으면 관리할 수 없다.
호출 1건이 한 줄이고, 상품 텍스트는 남기지 않는다(식별자와 숫자만).

총계 보기:

    python -m app.usage
"""

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config.catalog import CHAT_MODELS

# 테스트에서 monkeypatch로 바꿔 쓰므로 모듈 전역으로 둔다.
USAGE_LOG = Path(__file__).resolve().parent.parent / "logs" / "usage.jsonl"

# 카테캠 엘리스 ML API Serverless 단가(1M 토큰당 KRW). 단가·출처는 config/catalog.py에서 관리
PRICING_KRW = {model_id: asdict(model.price) for model_id, model in CHAT_MODELS.items() if model.price}


@dataclass(frozen=True)
class CallUsage:
    """호출 1건의 토큰 사용량. cached·cache_write는 input_tokens에, reasoning은 output_tokens에 포함된 값이다.

    게이트웨이는 캐시 쓰기 토큰을 1.25배로 쳐서 input_tokens에 넣어 보고함 (2026-10-14 실호출, Luna·Claude).
    비용은 input_tokens로 계산하면 쓰기 할증까지 들어감.
    """

    reported_model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    # 추론 모델이 답 전에 쓴 토큰. 출력 단가로 과금되어 비용 계산은 output_tokens로 충분, 강도별 비교용
    reasoning_tokens: int = 0
    # 이번 호출로 캐시에 새로 쓴 프롬프트 토큰 (다음 호출부터 적중 대상)
    cache_write_tokens: int = 0

    @property
    def uncached_input(self) -> int:
        """캐시 미적중 입력 토큰 (단가가 달라 따로 계산). 0 미만이면 0."""
        return max(self.input_tokens - self.cached_tokens, 0)

    @property
    def total_tokens(self) -> int:
        """입력 + 출력 토큰."""
        return self.input_tokens + self.output_tokens

    @property
    def cache_hit_rate(self) -> float | None:
        """입력 중 캐시 적중 비율. 입력이 없으면 None."""
        return round(self.cached_tokens / self.input_tokens, 4) if self.input_tokens else None


def from_handler(handler) -> CallUsage | None:
    """UsageMetadataCallbackHandler에서 사용량을 뽑는다. 모델별 집계를 합침.

    Args:
        handler: 호출에 쓴 콜백 핸들러.

    Returns:
        CallUsage | None: 사용량. 실제 호출이 없었으면(테스트 스텁 등) None.
    """
    metadata = getattr(handler, "usage_metadata", None) or {}
    if not metadata:
        return None
    models = ", ".join(sorted(metadata))
    total_in = total_cached = total_out = total_reasoning = total_write = 0
    for entry in metadata.values():
        total_in += entry.get("input_tokens", 0) or 0
        total_out += entry.get("output_tokens", 0) or 0
        # 프록시가 캐시 적중분을 알려준다. 없을 수도 있어 기본값을 둔다.
        total_cached += (entry.get("input_token_details") or {}).get("cache_read", 0) or 0
        total_reasoning += (entry.get("output_token_details") or {}).get("reasoning", 0) or 0
        total_write += (entry.get("input_token_details") or {}).get("cache_creation", 0) or 0
    return CallUsage(models, total_in, total_cached, total_out, total_reasoning, total_write)


def from_response(raw) -> CallUsage | None:
    """구조화 출력의 원본 응답(AIMessage)에서 사용량을 뽑는다.

    게이트웨이 최종 사용량(``response_metadata["token_usage"]``)을 먼저, 없으면 ``usage_metadata``를 씀.
    게이트웨이 값은 LangChain이 놓치는 Gemini 사용량·Claude 캐시까지 담음 (2026-10-14 실호출).

    Args:
        raw: ``include_raw=True`` 결과의 원본 응답.

    Returns:
        CallUsage | None: 사용량. 둘 다 없으면(테스트 스텁 등) None.
    """
    metadata = getattr(raw, "response_metadata", None) or {}
    gateway = metadata.get("token_usage") or {}
    usage = getattr(raw, "usage_metadata", None) or {}
    # 입력·출력이 다 있는 최종 사용량일 때만 (일부만 있는 값은 LangChain 값으로)
    if gateway.get("prompt_tokens") is not None and gateway.get("completion_tokens") is not None:
        prompt_details = gateway.get("prompt_tokens_details") or {}
        return CallUsage(
            reported_model=metadata.get("model_name") or "",
            input_tokens=gateway.get("prompt_tokens") or 0,
            cached_tokens=prompt_details.get("cached_tokens") or gateway.get("cached_prompt_tokens") or 0,
            output_tokens=gateway.get("completion_tokens") or 0,
            reasoning_tokens=(gateway.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
            cache_write_tokens=prompt_details.get("cache_write_tokens") or gateway.get("cache_write_tokens") or 0,
        )
    if not usage:
        return None
    details = usage.get("input_token_details") or {}
    return CallUsage(
        reported_model=metadata.get("model_name") or "",
        input_tokens=usage.get("input_tokens", 0) or 0,
        cached_tokens=details.get("cache_read") or gateway.get("cached_prompt_tokens") or 0,
        output_tokens=usage.get("output_tokens", 0) or 0,
        reasoning_tokens=(usage.get("output_token_details") or {}).get("reasoning", 0) or 0,
        cache_write_tokens=details.get("cache_creation") or gateway.get("cache_write_tokens") or 0,
    )


def from_completion(completion) -> CallUsage | None:
    """출력이 잘린 호출(길이 초과·콘텐츠 필터 예외)의 ChatCompletion에서 사용량을 뽑는다.

    Args:
        completion: 예외의 ``completion`` 속성 (openai ChatCompletion).

    Returns:
        CallUsage | None: 사용량. usage가 없으면 None.
    """
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    # 게이트웨이 공통 필드(cached_prompt_tokens·cache_write_tokens)는 usage 바로 아래에 올 수 있음
    cached = getattr(prompt_details, "cached_tokens", 0) or getattr(usage, "cached_prompt_tokens", 0)
    cache_write = getattr(prompt_details, "cache_write_tokens", 0) or getattr(usage, "cache_write_tokens", 0)
    return CallUsage(
        reported_model=getattr(completion, "model", None) or "",
        input_tokens=usage.prompt_tokens or 0,
        cached_tokens=cached or 0,
        output_tokens=usage.completion_tokens or 0,
        reasoning_tokens=getattr(completion_details, "reasoning_tokens", 0) or 0,
        cache_write_tokens=cache_write or 0,
    )


def estimate_krw(usage: CallUsage, configured_model: str | None) -> float | None:
    """카테캠 ML API 단가로 예상 비용을 계산한다.

    Args:
        usage: 사용량.
        configured_model: 단가표에서 찾을 모델 이름.

    Returns:
        float | None: 예상 비용(원). 단가를 모르면 None.
    """
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
    reasoning_effort: str | None = None,
    subject_id: str | None = None,
    ok: bool = True,
    elapsed_ms: int | None = None,
    error_type: str | None = None,
) -> None:
    """호출 1건을 JSONL 한 줄로 기록한다. 기록 실패는 무시 (호출 결과에 영향 없음).

    Args:
        agent: 기록 이름.
        usage: 사용량. 호출 실패로 모르면 None.
        configured_model: 비용 계산용 모델 이름.
        reasoning_effort: 추론 강도.
        subject_id: 기록 대상 ID (상품 ID).
        ok: 성공 여부.
        elapsed_ms: 걸린 시간(ms).
        error_type: 실패 원인 예외 이름 (메시지는 남기지 않음).
    """
    try:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "agent": agent,
            "configured_model": configured_model,
            # 같은 모델도 추론 강도에 따라 토큰·비용이 달라 함께 남김
            "reasoning_effort": reasoning_effort,
            # 프록시가 실제로 돌린 모델. 요청한 모델과 다른지 확인할 수 있다.
            "reported_model": usage.reported_model if usage else None,
            "input_tokens": usage.input_tokens if usage else None,
            "cached_input_tokens": usage.cached_tokens if usage else None,
            "cache_write_tokens": usage.cache_write_tokens if usage else None,
            "cache_hit_rate": usage.cache_hit_rate if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "reasoning_tokens": usage.reasoning_tokens if usage else None,
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
    """기록된 호출을 전체·에이전트별로 합산한다. 깨진 줄은 건너뜀.

    Args:
        path: 기록 파일. None이면 USAGE_LOG.

    Returns:
        dict: 호출·실패 수, 토큰, 예상 비용, 캐시 적중률, 에이전트별 집계.
    """
    target = path or USAGE_LOG
    totals = {
        "calls": 0,
        "failed": 0,
        "input": 0,
        "cached": 0,
        "cache_write": 0,
        "output": 0,
        "reasoning": 0,
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
        totals["cache_write"] += row.get("cache_write_tokens") or 0
        totals["reasoning"] += row.get("reasoning_tokens") or 0
        krw = row.get("estimated_cost_krw", row.get("est_krw")) or 0
        totals["est_krw"] += krw
        agent = row.get("agent") or "unknown"
        bucket = totals["by_agent"].setdefault(agent, {"calls": 0, "est_krw": 0.0, "input": 0, "cached": 0})
        bucket["calls"] += 1
        bucket["est_krw"] = round(bucket["est_krw"] + krw, 4)
        bucket["input"] += row.get("input_tokens", row.get("input")) or 0
        bucket["cached"] += row.get("cached_input_tokens", row.get("cached")) or 0
    totals["est_krw"] = round(totals["est_krw"], 2)
    # 전체·에이전트별 캐시 적중률 (입력 중 캐시 적중 비율)
    totals["cache_hit_rate"] = round(totals["cached"] / totals["input"], 4) if totals["input"] else None
    for bucket in totals["by_agent"].values():
        bucket["cache_hit_rate"] = round(bucket["cached"] / bucket["input"], 4) if bucket["input"] else None
    return totals


def main() -> int:
    """사용량 총계를 출력한다 (``python -m app.usage``).

    Returns:
        int: 종료 코드. 항상 0.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    totals = summarize()
    if totals["calls"] == 0:
        print(f"기록이 없습니다: {USAGE_LOG}")
        return 0
    cached_ratio = (totals["cache_hit_rate"] or 0) * 100
    print(f"기록 파일: {USAGE_LOG}")
    print(f"호출 {totals['calls']}회 (실패 {totals['failed']}회)")
    print(f"입력 {totals['input']:,} 토큰 (캐시 적중 {totals['cached']:,} = {cached_ratio:.0f}%, 캐시 쓰기 {totals['cache_write']:,})")
    print(f"출력 {totals['output']:,} 토큰 (추론 {totals['reasoning']:,})")
    print(f"예상 비용 {totals['est_krw']:,.2f}원  <- 카테캠 ML API 표시 단가 기준입니다")
    for agent, bucket in sorted(totals["by_agent"].items()):
        hit = f", 캐시 적중 {bucket['cache_hit_rate'] * 100:.0f}%" if bucket["cache_hit_rate"] is not None else ""
        print(f"  {agent}: {bucket['calls']}회, {bucket['est_krw']:,.2f}원{hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
