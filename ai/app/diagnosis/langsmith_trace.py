"""진단을 LangSmith 실행으로 묶음.

모델 호출은 LangChain이 자동으로 보냄. 여기서는 그 호출을 단계·Tool별로 묶고 이름만 붙임.
로컬 trace 파일(observability/trace.py)과 별개로 동작함.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from langsmith import trace

from ..pipeline.hooks import StageName
from ..schemas.schemas import ToolName

T = TypeVar("T")


def _traced(name: str, run_type: str, call: Callable[[], T], **options: Any) -> T:
    """호출 하나를 LangSmith 실행 하나로 감싼다.

    Args:
        name: 화면에 보일 이름.
        run_type: LangSmith 실행 종류.
        call: 실제 호출.
        **options: trace 추가 인자.

    Returns:
        T: 호출 결과.
    """
    with trace(name, run_type, **options) as run:
        result = call()
        run.end(outputs={"output": result})
        return result


def stage_hook(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
    """단계를 LangSmith 실행으로 감싼다. 재실행 회차는 이름으로 구분함.

    Args:
        stage: 단계 이름.
        retry_round: 회차. 최초 실행은 0.
        call: 실제 단계 호출.

    Returns:
        T: 단계 결과.
    """
    return _traced(f"{stage} #{retry_round}" if retry_round else stage, "chain", call)


def tool_hook(tool_name: ToolName, call: Callable[[], Any], /) -> Any:
    """Tool을 LangSmith 실행으로 감싼다.

    Args:
        tool_name: Tool 이름.
        call: 실제 Tool 호출.

    Returns:
        Any: Tool이 돌려준 값.
    """
    return _traced(f"tool:{tool_name.value}", "tool", call)
