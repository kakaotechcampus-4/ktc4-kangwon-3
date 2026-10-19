"""에이전트 모델 호출 1건의 사용량 기록·콘솔 로그. 응답 → 사용량 변환은 공용 app/usage.py."""

import logging
from time import perf_counter
from typing import Any

from ...usage import CallUsage, record

logger = logging.getLogger(__name__)


def record_call(
    agent: str,
    usage: CallUsage | None,
    *,
    configured_model: str | None,
    reasoning_effort: str | None,
    subject_id: str,
    started_at: float,
    error_type: str | None = None,
) -> None:
    """호출 1건을 공용 사용량 로그에 남긴다. 기록 실패는 호출 결과에 영향 없음.

    Args:
        agent: 사용량 기록 이름.
        usage: 응답에서 읽은 사용량. 호출 자체가 실패해 모르면 None.
        configured_model: 비용 계산에 쓸 모델 이름.
        reasoning_effort: 추론 강도. 스텁·주입 모델은 None.
        subject_id: 기록 대상 ID (상품 ID).
        started_at: 호출 시작 시각 (perf_counter). 걸린 시간 계산용.
        error_type: 실패 원인 예외 이름. 성공이면 None.
    """
    record(
        agent,
        usage,
        configured_model=configured_model,
        reasoning_effort=reasoning_effort,
        subject_id=subject_id,
        ok=error_type is None,
        elapsed_ms=round((perf_counter() - started_at) * 1000),
        error_type=error_type,
    )


def log_token_usage(component_name: str, usage: CallUsage | None, raw_message: Any) -> None:
    """수집한 사용량을 콘솔 로그로 출력한다. 출력 실패는 판정에 영향 없음.

    cache_read가 계속 0이면 프롬프트 캐시가 안 먹는 것. 고정 prefix가 호출마다 바뀌는지 확인.

    Args:
        component_name: 로그에 표시할 에이전트 이름.
        usage: 사용량. None이면 아무것도 안 함.
        raw_message: 원본 응답. 게이트웨이 원본 usage를 디버그 로그로 남길 때 씀.
    """
    if usage is None:
        return
    try:
        hit_rate = "-" if usage.cache_hit_rate is None else f"{usage.cache_hit_rate:.1%}"
        logger.info(
            "%s 토큰 사용량 input=%s (cache_read=%s, cache_write=%s, 적중률 %s) output=%s (reasoning=%s) total=%s",
            component_name,
            usage.input_tokens,
            usage.cached_tokens,
            usage.cache_write_tokens,
            hit_rate,
            usage.output_tokens,
            usage.reasoning_tokens,
            usage.total_tokens,
        )
        # 게이트웨이 원본 필드명이 OpenAI와 다를 수 있어 디버그로 남김
        response_metadata = getattr(raw_message, "response_metadata", None) or {}
        if response_metadata.get("token_usage"):
            logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
    except Exception:
        pass
