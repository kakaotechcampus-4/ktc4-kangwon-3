"""hook 기본값과 묶기: 앞 hook이 바깥, 안쪽은 바꿔치기·예외까지 그대로 전달."""

import pytest

from app.pipeline.hooks import chain_stage_hooks, chain_tool_hooks, no_stage_hook, no_tool_hook
from app.schemas.schemas import ToolName


def _recording_stage_hook(name, events):
    def hook(stage, retry_round, call):
        events.append(f"{name} 시작 {stage} {retry_round}")
        try:
            return call()
        finally:
            events.append(f"{name} 끝")

    return hook


def _recording_tool_hook(name, events):
    def hook(tool_name, call):
        events.append(f"{name} 시작 {tool_name.value}")
        try:
            return call()
        finally:
            events.append(f"{name} 끝")

    return hook


def test_기본_hook은_호출_결과를_그대로_돌려준다():
    assert no_stage_hook("selection", 0, lambda: "결과") == "결과"
    assert no_tool_hook(ToolName.CUSTOMS, lambda: "결과") == "결과"


def test_빈_묶음은_호출만_한다():
    assert chain_stage_hooks()("selection", 0, lambda: "결과") == "결과"
    assert chain_tool_hooks()(ToolName.CUSTOMS, lambda: "결과") == "결과"


def test_단계_hook은_앞이_바깥이고_단계·회차를_모두_받는다():
    events = []
    hook = chain_stage_hooks(_recording_stage_hook("바깥", events), _recording_stage_hook("안쪽", events))

    result = hook("verification", 2, lambda: events.append("단계") or "결과")

    assert result == "결과"
    assert events == ["바깥 시작 verification 2", "안쪽 시작 verification 2", "단계", "안쪽 끝", "바깥 끝"]


def test_안쪽_hook이_바꿔치기한_결과를_바깥_hook이_받는다():
    events = []

    def replace(stage, retry_round, call):
        return "저장한 결과"

    def outer(stage, retry_round, call):
        result = call()
        events.append(result)
        return result

    result = chain_stage_hooks(outer, replace)("extraction", 0, lambda: events.append("단계") or "결과")

    assert result == "저장한 결과"
    assert events == ["저장한 결과"]


def test_단계_예외는_모든_hook을_거쳐_그대로_올라간다():
    events = []
    hook = chain_stage_hooks(_recording_stage_hook("바깥", events), _recording_stage_hook("안쪽", events))

    def fail():
        raise ValueError("단계 실패")

    with pytest.raises(ValueError, match="단계 실패"):
        hook("aggregation", 1, fail)
    assert events == ["바깥 시작 aggregation 1", "안쪽 시작 aggregation 1", "안쪽 끝", "바깥 끝"]


def test_Tool_hook은_앞이_바깥이고_Tool_이름을_받는다():
    events = []
    hook = chain_tool_hooks(_recording_tool_hook("바깥", events), _recording_tool_hook("안쪽", events))

    result = hook(ToolName.CUSTOMS, lambda: events.append("Tool") or "결과")

    assert result == "결과"
    assert events == [f"바깥 시작 {ToolName.CUSTOMS.value}", f"안쪽 시작 {ToolName.CUSTOMS.value}", "Tool", "안쪽 끝", "바깥 끝"]
