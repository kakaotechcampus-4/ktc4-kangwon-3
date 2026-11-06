"""진행 알림 hook: 단계 알림, Tool started·completed·skipped."""

from types import SimpleNamespace

import pytest

from app.diagnosis.progress import ProgressStageHook, ProgressToolHook
from app.domain.context import PipelineStage
from app.pipeline.hooks import chain_stage_hooks
from app.pipeline.tool_executor import ToolExecutor
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.pipeline import RetryRequest
from app.schemas.product import Product
from app.schemas.schemas import ToolName, ToolResult, ToolStatus, VerificationResult, VerificationStatus


class _Progress:
    def __init__(self):
        self.events = []

    def stage(self, stage):
        self.events.append(stage)

    def tool(self, tool_name, status):
        self.events.append((tool_name, status))


class _FakeTool:
    def __init__(self, tool_name, failing=False):
        self.tool_name = tool_name
        self.failing = failing

    def execute(self, product, decision):
        if self.failing:
            raise RuntimeError("조회 실패")
        return ToolResult(tool_name=self.tool_name, status=ToolStatus.SUCCESS, selected=True,
                          selection_reason=decision.reason)


def _selection(selected):
    return ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=name, selected=name in selected, reason="이유") for name in ToolName])


def _tool_execution(progress, failing=frozenset()):
    """진행 알림 hook을 붙인 Tool 실행 단계 (최초·재실행)."""
    tools = {name: _FakeTool(name, failing=name in failing) for name in ToolName}
    executor = ToolExecutor(tools, max_parallel=1, tool_hook=ProgressToolHook(progress))
    stage_hook = chain_stage_hooks(ProgressStageHook(progress))
    initial = lambda product, selection: stage_hook(  # noqa: E731
        "tool_execution", 0, lambda: executor.execute_initial(product, selection))
    retry = lambda product, previous, request: stage_hook(  # noqa: E731
        "tool_execution", request.retry_round, lambda: executor.execute_retry(product, previous, request))
    return initial, retry


def test_단계를_부르기_전에_단계_알림을_보낸다():
    progress = _Progress()
    hook = ProgressStageHook(progress)

    result = hook("aggregation", 2, lambda: progress.events.append("단계") or "결과")

    assert result == "결과"
    assert progress.events == [PipelineStage.AGGREGATION, "단계"]


def test_첫_실행은_선택한_Tool마다_시작·완료를_보내고_나머지는_건너뜀을_보낸다():
    progress = _Progress()
    initial, _ = _tool_execution(progress)

    initial(Product(product_id="p-1"), _selection({ToolName.RADIO}))

    assert progress.events[:3] == [
        PipelineStage.TOOL_EXECUTION, (ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]
    assert sorted(progress.events[3:]) == sorted((name, "skipped") for name in ToolName if name is not ToolName.RADIO)


def test_Tool이_예외를_내도_완료를_보낸다():
    progress = _Progress()
    hook = ProgressToolHook(progress)

    def fail():
        raise RuntimeError("조회 실패")

    with pytest.raises(RuntimeError):
        hook(ToolName.RADIO, fail)

    assert progress.events == [(ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]


def test_Tool이_예외를_내도_실행기는_실패_결과로_남긴다():
    progress = _Progress()
    initial, _ = _tool_execution(progress, failing={ToolName.RADIO})

    result = initial(Product(product_id="p-1"), _selection({ToolName.RADIO}))

    assert progress.events[1:3] == [(ToolName.RADIO, "started"), (ToolName.RADIO, "completed")]
    radio = next(r for r in result.tool_results if r.tool_name is ToolName.RADIO)
    assert radio.status is ToolStatus.FAILED


def test_재실행_회차는_다시_실행하는_Tool만_시작·완료를_보내고_건너뜀은_다시_보내지_않는다():
    progress = _Progress()
    initial, retry = _tool_execution(progress)
    product = Product(product_id="p-1")
    first = initial(product, _selection({ToolName.RADIO}))
    progress.events.clear()
    verification = VerificationResult(status=VerificationStatus.TOOLS_REQUIRED,
                                      additional_tools_required=[ToolName.CUSTOMS])
    request = RetryRequest(retry_round=1, requested_tools=[ToolName.CUSTOMS], verification=verification,
                           latest_tool_results=first.tool_results)

    retry(product, first, request)

    assert progress.events == [
        PipelineStage.TOOL_EXECUTION, (ToolName.CUSTOMS, "started"), (ToolName.CUSTOMS, "completed")]


def test_Tool_실행이_아닌_단계는_결과를_열어_보지_않는다():
    progress = _Progress()

    ProgressStageHook(progress)("aggregation", 0, lambda: SimpleNamespace())

    assert progress.events == [PipelineStage.AGGREGATION]
