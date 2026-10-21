"""에이전트 실행 기록 등록표: 등록·해제, 임시 등록, sink 오류 격리를 확인한다."""

import pytest

from app.agents.base import AgentRunMeta
from app.observability.agent_sinks import AgentSinkRegistry

_META = AgentRunMeta(component="extraction", model="gpt-5-mini", elapsed_ms=120)


class _Recorder:
    def __init__(self) -> None:
        self.records: list[tuple[AgentRunMeta, str]] = []

    def __call__(self, meta: AgentRunMeta, subject_id: str) -> None:
        self.records.append((meta, subject_id))


def test_등록된_sink_전부에_기록을_넘긴다():
    registry, first, second = AgentSinkRegistry(), _Recorder(), _Recorder()
    registry.add(first)
    registry.add(second)

    registry.publish(_META, "p-1")

    assert first.records == second.records == [(_META, "p-1")]


def test_같은_sink를_두_번_등록해도_한_번만_받는다():
    registry, recorder = AgentSinkRegistry(), _Recorder()
    registry.add(recorder)
    registry.add(recorder)

    registry.publish(_META, "p-1")

    assert len(recorder.records) == 1


def test_해제한_sink는_받지_않고_없는_sink_해제는_무시한다():
    registry, recorder = AgentSinkRegistry(), _Recorder()
    registry.add(recorder)

    registry.remove(recorder)
    registry.remove(recorder)
    registry.publish(_META, "p-1")

    assert recorder.records == []


def test_임시_등록은_블록이_끝나면_해제된다():
    registry, recorder = AgentSinkRegistry(), _Recorder()

    with registry.added(recorder):
        registry.publish(_META, "p-1")
    registry.publish(_META, "p-2")

    assert [subject_id for _, subject_id in recorder.records] == ["p-1"]


def test_임시_등록은_예외로_빠져나가도_해제된다():
    registry, recorder = AgentSinkRegistry(), _Recorder()

    with pytest.raises(RuntimeError), registry.added(recorder):
        raise RuntimeError("평가 실패")
    registry.publish(_META, "p-1")

    assert recorder.records == []


def test_sink_오류는_경고만_남기고_나머지_sink에_계속_넘긴다(caplog):
    registry, recorder = AgentSinkRegistry(), _Recorder()

    def broken(meta, subject_id):
        raise ValueError("기록 실패")

    registry.add(broken)
    registry.add(recorder)

    registry.publish(_META, "p-1")

    assert recorder.records == [(_META, "p-1")]
    assert "sink 처리 실패" in caplog.text
