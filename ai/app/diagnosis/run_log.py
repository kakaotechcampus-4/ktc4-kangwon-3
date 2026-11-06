"""진단 실행 로그 hook."""

from collections.abc import Callable
from typing import TypeVar

from ..observability.logs import set_run_field
from ..pipeline.hooks import StageName

T = TypeVar("T")


def mark_retry_round(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
    """재실행 회차부터 이후 로그 줄(재실행 Tool·집계·검증)에 회차 표시. 단계 hook."""
    if retry_round:
        set_run_field("retry_round", retry_round)
    return call()
