"""LLM 호출 1건의 사용량을 측정해 공용 사용량 로그에 남긴다.

호출하는 쪽(에이전트, 평가 러너 등)과 무관하게 호출 1건마다 소요시간·토큰·성공 여부를
한 번만 기록한다. 기록 형식과 지표는 ``usage.record()``를 따른다.

    with track_llm_call("extraction", configured_model=..., subject_id=...) as call:
        result = model.invoke(messages, config={"callbacks": call.callbacks})
        call.use_response(result["raw"])
        if result["parsing_error"] is not None:
            call.fail(type(result["parsing_error"]).__name__)
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler

from . import usage

_logger = logging.getLogger(__name__)


class LLMCall:
    """``track_llm_call()`` 블록 안에서 쓰는 호출 1건의 측정 상태."""

    def __init__(self) -> None:
        self._handler = UsageMetadataCallbackHandler()
        self._response: Any = None
        self.error_type: str | None = None

    @property
    def callbacks(self) -> list:
        """모델 호출의 ``config={"callbacks": ...}``에 넘길 콜백 목록."""
        return [self._handler]

    def use_response(self, raw: Any) -> None:
        """원본 응답(AIMessage)을 알린다. 토큰은 콜백보다 이 응답을 먼저 쓴다.

        Args:
            raw: ``with_structured_output(include_raw=True)``의 ``raw`` 값.
        """
        self._response = raw

    def fail(self, error_type: str) -> None:
        """응답은 받았지만 결과로 쓸 수 없을 때 실패로 표시한다. 토큰은 그대로 기록한다.

        Args:
            error_type: 실패 원인 이름 (예외 타입 이름 등).
        """
        self.error_type = error_type

    def measured_usage(self) -> usage.CallUsage | None:
        """원본 응답의 사용량, 없으면 콜백이 모은 사용량. 둘 다 없으면 None."""
        return usage.from_response(self._response) or usage.from_handler(self._handler)


@contextmanager
def track_llm_call(
    name: str,
    *,
    configured_model: str | None = None,
    subject_id: str | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[LLMCall]:
    """블록 안의 LLM 호출 1건을 측정하고, 블록이 끝나면 사용량 로그에 한 줄 남긴다.

    블록 안에서 예외가 나면 실패로 기록한 뒤 예외를 그대로 다시 던진다.

    Args:
        name: 사용량 로그의 호출 주체 이름 (예: "extraction", "extraction-eval").
        configured_model: 비용 계산에 쓸 설정 모델 이름.
        subject_id: 호출 대상 식별자 (예: product_id).
        logger: 토큰 사용량 콘솔 로그를 남길 로거. None이면 이 모듈 로거.

    Yields:
        LLMCall: 콜백 목록과 원본 응답·실패를 알리는 측정 상태.
    """
    call = LLMCall()
    started_at = perf_counter()
    try:
        yield call
    except Exception as exc:
        if call.error_type is None:
            call.fail(type(exc).__name__)
        raise
    finally:
        measured = call.measured_usage()
        usage.record(
            name,
            measured,
            configured_model=configured_model,
            subject_id=subject_id,
            ok=call.error_type is None,
            elapsed_ms=round((perf_counter() - started_at) * 1000),
            error_type=call.error_type,
        )
        _log_usage(logger or _logger, name, measured, call._response)


def _log_usage(
    logger: logging.Logger,
    name: str,
    measured: usage.CallUsage | None,
    raw: Any,
) -> None:
    """토큰 사용량을 INFO로 남긴다. cache_read가 계속 0이면 프롬프트 캐시가 안 먹는 상태.

    Args:
        logger: 로그를 남길 로거.
        name: 호출 주체 이름.
        measured: 측정한 사용량. None이면 남기지 않음.
        raw: 원본 응답. 게이트웨이 원본 usage를 DEBUG로 남길 때 사용.
    """
    if measured is None:
        return
    logger.info(
        "%s 토큰 사용량 input=%s (cache_read=%s) output=%s total=%s",
        name,
        measured.input_tokens,
        measured.cached_tokens,
        measured.output_tokens,
        measured.total_tokens,
    )
    # 게이트웨이(엘리스 MLAPI) 원본 필드명 확인용
    response_metadata = getattr(raw, "response_metadata", None) or {}
    if response_metadata.get("token_usage"):
        logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
