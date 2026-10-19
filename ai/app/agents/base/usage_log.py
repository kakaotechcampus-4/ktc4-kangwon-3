"""에이전트 모델 호출 1건의 사용량 기록·콘솔 로그. 응답 → 사용량 변환은 app/usage.py."""

import logging
from typing import Any

from ... import usage as usage_module
from ...usage import CallUsage

logger = logging.getLogger(__name__)


def record_call(
    agent: str,
    usage: CallUsage | None,
    *,
    configured_model: str | None,
    reasoning_effort: str | None,
    subject_id: str,
    elapsed_ms: int,
    error_type: str | None = None,
    failure_phase: str | None = None,
) -> None:
    """호출 1건을 공용 사용량 로그에 남긴다. 기록 실패는 호출 결과에 영향 없음.

    Args:
        agent: 사용량 기록 이름.
        usage: 사용량. 호출 실패로 모르면 None.
        configured_model: 비용 계산용 모델 이름.
        reasoning_effort: 추론 강도. 스텁·주입 모델은 None.
        subject_id: 기록 대상 ID (상품 ID).
        elapsed_ms: 걸린 시간(ms).
        error_type: 실패 원인 예외 이름. 성공이면 None.
        failure_phase: 실패 단계 (call·parsing·finalize). 성공이면 None.
    """
    # 모듈 속성으로 찾음 → app.usage.record 바꿔치기(테스트·평가 러너 사용량 캡처)가 먹힘
    usage_module.record(
        agent,
        usage,
        configured_model=configured_model,
        reasoning_effort=reasoning_effort,
        subject_id=subject_id,
        ok=error_type is None,
        elapsed_ms=elapsed_ms,
        error_type=error_type,
        failure_phase=failure_phase,
    )


def log_token_usage(component_name: str, usage: CallUsage | None, raw_message: Any) -> None:
    """사용량을 콘솔 로그로 남긴다. 실패해도 무시. cache_read가 계속 0이면 프롬프트 캐시 미적중.

    Args:
        component_name: 에이전트 이름.
        usage: 사용량. None이면 생략.
        raw_message: 원본 응답. 게이트웨이 원본 usage 디버그 로그용.
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
        response_metadata = getattr(raw_message, "response_metadata", None) or {}
        # 게이트웨이 원본 usage가 있으면 필드명 대조용 디버그 로그
        if response_metadata.get("token_usage"):
            logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
    except Exception:
        # 사용량 객체·응답 모양이 예상과 달라 로그 포맷 실패 → 판정에 영향 없게 무시
        pass
