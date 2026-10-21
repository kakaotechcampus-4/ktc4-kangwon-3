"""에이전트 모델 호출 1건의 사용량 기록·콘솔 로그. 응답 → 사용량 변환은 app/usage.py.

record_call은 sink 등록표(observability/agent_sinks)에 기본 등록되는 사용량 로그(usage.jsonl) sink.
서버·CLI·평가 어디서 불려도 기존처럼 로그가 남도록 import 시점에 등록함.
"""

import logging
from typing import Any

from ... import usage as usage_module
from ...observability.agent_sinks import agent_sinks
from ...usage import CallUsage
from .meta import AgentRunMeta

logger = logging.getLogger(__name__)


def record_call(meta: AgentRunMeta, subject_id: str) -> None:
    """호출 1건을 공용 사용량 로그에 남긴다. 기록 실패는 호출 결과에 영향 없음.

    Args:
        meta: 호출 1건의 실행 정보. 기록 이름은 usage_name, 없으면 component.
        subject_id: 기록 대상 ID (상품 ID).
    """
    # 모듈 속성으로 찾음 → app.usage.record 바꿔치기(테스트·평가 러너 사용량 캡처)가 먹힘
    usage_module.record(
        meta.usage_name or meta.component,
        meta.usage,
        configured_model=meta.model,
        reasoning_effort=meta.reasoning_effort,
        subject_id=subject_id,
        ok=meta.error_type is None,
        elapsed_ms=meta.elapsed_ms,
        error_type=meta.error_type,
        failure_phase=meta.failure_phase,
    )


agent_sinks.add(record_call)


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
