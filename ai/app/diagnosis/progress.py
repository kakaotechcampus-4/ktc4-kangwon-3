"""진행 알림 hook. 단계 시작과 Tool 진행(started·completed·skipped)을 세션 진행 알림으로 보냄.

재실행 회차에도 단계 알림은 다시 나감. Tool 진행은 다시 실행하는 Tool만 started·completed, skipped는 첫 회차만.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from ..domain.context import PipelineStage
from ..pipeline.hooks import StageName
from ..schemas.schemas import ToolName, ToolStatus
from ..sessions.job import ProgressReporter

T = TypeVar("T")


class ProgressStageHook:
    """단계를 부르기 전에 단계 알림, 첫 Tool 실행 뒤엔 선택 안 된 Tool에 skipped 알림."""

    def __init__(self, progress: ProgressReporter) -> None:
        """
        Args:
            progress: 이번 실행의 진행 알림.
        """
        self._progress = progress

    def __call__(self, stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
        self._progress.stage(PipelineStage(stage))
        result = call()
        # 선택 안 된 Tool은 실행기가 부르지 않아 Tool hook이 못 봄
        if stage == "tool_execution" and retry_round == 0:
            for tool_result in result.tool_results:  # type: ignore[attr-defined]
                if tool_result.status is ToolStatus.SKIPPED:
                    self._progress.tool(tool_result.tool_name, "skipped")
        return result


class ProgressToolHook:
    """선택된 Tool 실행 전후로 started·completed 알림. Tool 예외도 completed (실패 여부는 분야 카드에서 표시)."""

    def __init__(self, progress: ProgressReporter) -> None:
        """
        Args:
            progress: 이번 실행의 진행 알림.
        """
        self._progress = progress

    def __call__(self, tool_name: ToolName, call: Callable[[], Any], /) -> Any:
        self._progress.tool(tool_name, "started")
        try:
            return call()
        finally:
            self._progress.tool(tool_name, "completed")
