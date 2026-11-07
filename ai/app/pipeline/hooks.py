"""단계·Tool 호출을 감싸는 hook 계약.

hook은 호출 하나를 받아 앞뒤에 공통 관심사(진행 알림·trace·로그 등)를 붙이고 결과를 돌려줌.
호출을 안 부르고 다른 결과로 바꿔치기할 수도 있음 (단계 다시 실행). 업무 로직은 hook에 두지 않음.
구현은 쓰는 쪽(diagnosis/)에, 여기엔 계약·기본값·묶기만.
"""

from collections.abc import Callable
from functools import partial
from typing import Any, Literal, Protocol, TypeVar

from ..schemas.schemas import ToolName

T = TypeVar("T")

StageName = Literal["extraction", "selection", "tool_execution", "aggregation", "verification"]


class StageHook(Protocol):
    """단계 호출 하나를 감쌈."""

    def __call__(self, stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
        """단계를 실행하고 결과를 돌려줌.

        Args:
            stage: 단계 이름.
            retry_round: 회차. 최초 실행은 0, 재실행은 1부터.
            call: 실제 단계 호출 (안쪽 hook 포함).

        Returns:
            T: 단계 결과.
        """
        ...


class ToolHook(Protocol):
    """선택된 Tool 호출 하나를 감쌈. Tool 실행 스레드 안에서 불림."""

    def __call__(self, tool_name: ToolName, call: Callable[[], Any], /) -> Any:
        """Tool을 실행하고 결과를 돌려줌.

        Args:
            tool_name: Tool 이름.
            call: 실제 Tool 호출 (안쪽 hook 포함).

        Returns:
            Any: Tool이 돌려준 값 (검증 전).
        """
        ...


def no_stage_hook(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
    """아무것도 안 붙이는 단계 hook."""
    return call()


def no_tool_hook(tool_name: ToolName, call: Callable[[], Any], /) -> Any:
    """아무것도 안 붙이는 Tool hook."""
    return call()


def chain_stage_hooks(*hooks: StageHook) -> StageHook:
    """단계 hook 여러 개를 하나로 묶음.

    Args:
        *hooks: 묶을 hook. 앞일수록 바깥.

    Returns:
        StageHook: 묶은 hook.
    """

    def chained(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
        # 안쪽 hook부터 감쌈
        for hook in reversed(hooks):
            call = partial(hook, stage, retry_round, call)
        return call()

    return chained


def chain_tool_hooks(*hooks: ToolHook) -> ToolHook:
    """Tool hook 여러 개를 하나로 묶음.

    Args:
        *hooks: 묶을 hook. 앞일수록 바깥.

    Returns:
        ToolHook: 묶은 hook.
    """

    def chained(tool_name: ToolName, call: Callable[[], Any], /) -> Any:
        # 안쪽 hook부터 감쌈
        for hook in reversed(hooks):
            call = partial(hook, tool_name, call)
        return call()

    return chained
