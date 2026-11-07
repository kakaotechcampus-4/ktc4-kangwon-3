"""진단 실행 로그 hook."""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from ..clients.base import mask_sensitive_params
from ..domain.errors import AIError
from ..observability.logs import set_run_field
from ..pipeline.hooks import StageName
from ..schemas.schemas import ToolName

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 로그에 남길 감싼 원인의 최대 단계 (Tool 오류 ← 조회 오류 ← HTTP 오류 정도면 충분)
_MAX_ERROR_CAUSES = 4


def error_text(exc: BaseException) -> str:
    """로그용 예외 설명. 감싼 원인(__cause__)까지 ← 로 이어 붙이고, 메시지 속 URL의 키는 가림.

    Tool은 외부 조회 오류를 공통 Tool 예외로 감싸므로 바깥 문장만으로는 실패 원인을 알 수 없다.

    Args:
        exc: 남길 예외.

    Returns:
        str: ``이름: 메시지 ← 이름: 메시지`` 형태의 설명.
    """
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) <= _MAX_ERROR_CAUSES:
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__
    return mask_sensitive_params(" ← ".join(parts))


def log_tool_failure(tool_name: ToolName, call: Callable[[], Any], /) -> Any:
    """Tool 실패 원인 로그. 예외는 그대로 올림 (실행기가 FAILED 결과로 바꿈). Tool hook.

    실행기는 원인을 남기지 않아 여기서 남김 (#497).
    """
    try:
        return call()
    except AIError as exc:
        # 예상한 실패(외부 API·모델·Tool 오류)는 원인만
        logger.warning("Tool 실행 실패 %s: %s", tool_name, error_text(exc))
        raise
    except Exception as exc:
        # 코드 오류 가능성 → 위치까지
        logger.error("Tool 실행 실패 %s: %s", tool_name, error_text(exc), exc_info=True)
        raise


def mark_retry_round(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
    """재실행 회차부터 이후 로그 줄(재실행 Tool·집계·검증)에 회차 표시. 단계 hook."""
    if retry_round:
        set_run_field("retry_round", retry_round)
    return call()
