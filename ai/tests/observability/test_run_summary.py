"""실행 요약 재료 모으기 테스트."""

from app.agents.base import AgentRunMeta
from app.domain.context import PipelineStage
from app.observability.agent_sinks import agent_sinks
from app.observability.measurements import ToolRun, measurement_sinks
from app.observability.run_summary import current_summary, run_summary
from app.usage import CallUsage

S = PipelineStage


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_단계_시간은_다음_단계에_들어갈_때_닫히고_재실행_회차의_같은_단계는_더한다():
    clock = _Clock()
    with run_summary(clock) as summary:
        for stage, seconds in [(S.EXTRACTION, 5), (S.TOOL_EXECUTION, 10), (S.VERIFICATION, 3),
                               (S.TOOL_EXECUTION, 4), (S.VERIFICATION, 2)]:
            summary.enter_stage(stage)
            clock.now += seconds
        total = summary.finish()

    assert summary.stage_seconds == {"extraction": 5, "tool_execution": 14, "verification": 5}
    assert summary.tool_execution_rounds == 2
    assert total == 24


def test_실행_중_Tool_실행_기록만_모으고_건너뜀은_뺀다():
    with run_summary() as summary:
        measurement_sinks.publish(ToolRun("electrical_safety", "success", 2.5))
        measurement_sinks.publish(ToolRun("radio", "skipped", 0.0))
        measurement_sinks.publish(ToolRun("customs", "failed", 1.0, error_type="client"))

    assert [(t.tool_name, t.status, t.seconds) for t in summary.tools] == [
        ("electrical_safety", "success", 2.5), ("customs", "failed", 1.0),
    ]


def test_모델_호출은_수·실패·토큰·비용을_더하고_단가_모르는_호출은_비용에서_뺀다():
    usage = CallUsage("openai/gpt-4.1-mini", input_tokens=100, cached_tokens=0, output_tokens=20)
    with run_summary() as summary:
        agent_sinks.publish(AgentRunMeta(component="extraction", usage=usage, cost_krw=1.5), "p-1")
        agent_sinks.publish(AgentRunMeta(component="selection", usage=usage), "p-1")
        agent_sinks.publish(AgentRunMeta(component="verification", error_type="TimeoutError"), "p-1")

    assert (summary.model_calls, summary.model_failures) == (3, 1)
    assert (summary.input_tokens, summary.output_tokens, summary.cost_krw) == (200, 40, 1.5)


def test_실행_밖의_기록은_무시한다():
    measurement_sinks.publish(ToolRun("radio", "success", 1.0))

    assert current_summary() is None
