"""진단 실행 하나의 요약 재료 모으기 (#497).

실행 중 단계 시간, Tool 실행 결과, 모델 호출을 모아 실행이 끝날 때 로그 한 줄로 남김.
Tool 실행·모델 호출은 이미 있는 측정 기록·에이전트 실행 기록 sink로 받고,
지금 실행의 요약은 문맥 변수로 찾음. 실행 밖(평가·CLI) 기록은 무시.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..domain.context import PipelineStage
from .agent_sinks import agent_sinks
from .measurements import Measurement, ToolRun, measurement_sinks

if TYPE_CHECKING:
    from ..agents.base.meta import AgentRunMeta


@dataclass
class ToolRunSummary:
    """요약에 넣을 Tool 실행 1건.

    Attributes:
        tool_name: Tool 이름.
        status: 실행 상태.
        seconds: 걸린 시간(초).
        round: Tool 실행 회차. 첫 회차 1, 재실행마다 1씩.
    """

    tool_name: str
    status: str
    seconds: float
    round: int = 1


@dataclass
class RunSummary:
    """실행 하나의 요약 재료. 실행 스레드 하나만 씀.

    Attributes:
        clock: 시각 함수(초). 테스트에서 바꿈.
        started: 실행 시작 시각.
        stage_seconds: 단계 → 걸린 시간 합(초). 재실행 회차의 같은 단계는 더함.
        tool_execution_rounds: Tool 실행 단계에 들어간 횟수. 첫 회차 1, 재실행마다 1씩.
        tools: Tool 실행 결과. 실행 순서대로, 건너뜀은 뺌.
        model_calls: 모델 호출 수.
        model_failures: 실패한 모델 호출 수.
        input_tokens: 입력 토큰 합.
        output_tokens: 출력 토큰 합.
        cost_krw: 예상 비용 합(원). 단가를 모르는 호출은 뺌.
    """

    clock: Callable[[], float] = time.perf_counter
    started: float = 0.0
    stage_seconds: dict[str, float] = field(default_factory=dict)
    tool_execution_rounds: int = 0
    tools: list[ToolRunSummary] = field(default_factory=list)
    model_calls: int = 0
    model_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_krw: float = 0.0
    _stage: str | None = None
    _stage_started: float = 0.0

    def __post_init__(self) -> None:
        self.started = self.clock()

    def enter_stage(self, stage: PipelineStage) -> None:
        """앞 단계 시간을 닫고 새 단계를 시작한다.

        Args:
            stage: 들어가는 단계.
        """
        self._close_stage()
        self._stage, self._stage_started = stage.value, self.clock()
        if stage is PipelineStage.TOOL_EXECUTION:
            self.tool_execution_rounds += 1

    def finish(self) -> float:
        """마지막 단계 시간을 닫고 총 시간을 돌려준다.

        Returns:
            float: 실행 시작부터 지금까지(초).
        """
        self._close_stage()
        self._stage = None
        return self.clock() - self.started

    def add_tool(self, run: ToolRun) -> None:
        """Tool 실행 1건을 지금 회차로 넣는다. 건너뜀은 시간이 없어 뺌.

        Args:
            run: Tool 실행 측정 기록.
        """
        if run.status != "skipped":
            self.tools.append(ToolRunSummary(run.tool_name, run.status, run.seconds, max(self.tool_execution_rounds, 1)))

    def add_call(self, meta: "AgentRunMeta") -> None:
        """모델 호출 1건을 더한다.

        Args:
            meta: 호출 1건의 실행 정보.
        """
        self.model_calls += 1
        if meta.error_type is not None:
            self.model_failures += 1
        if meta.usage is not None:
            self.input_tokens += meta.usage.input_tokens
            self.output_tokens += meta.usage.output_tokens
        if meta.cost_krw is not None:
            self.cost_krw += meta.cost_krw

    def _close_stage(self) -> None:
        if self._stage is not None:
            seconds = self.clock() - self._stage_started
            self.stage_seconds[self._stage] = self.stage_seconds.get(self._stage, 0.0) + seconds


_summary: ContextVar[RunSummary | None] = ContextVar("run_summary", default=None)


@contextmanager
def run_summary(clock: Callable[[], float] = time.perf_counter) -> Iterator[RunSummary]:
    """이 블록에서 일어난 단계·Tool·모델 호출을 새 요약에 모은다.

    Args:
        clock: 시각 함수(초).

    Yields:
        RunSummary: 이 실행의 요약.
    """
    summary = RunSummary(clock=clock)
    token = _summary.set(summary)
    try:
        yield summary
    finally:
        _summary.reset(token)


def current_summary() -> RunSummary | None:
    """지금 실행의 요약. 실행 밖이면 None.

    Returns:
        RunSummary | None: 요약.
    """
    return _summary.get()


def _on_measurement(record: Measurement) -> None:
    summary = _summary.get()
    if summary is not None and isinstance(record, ToolRun):
        summary.add_tool(record)


def _on_agent_call(meta: "AgentRunMeta", subject_id: str) -> None:
    summary = _summary.get()
    if summary is not None:
        summary.add_call(meta)


measurement_sinks.add(_on_measurement)
agent_sinks.add(_on_agent_call)
