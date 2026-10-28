"""측정 기록 등록표: 등록·해제, 임시 등록, sink 오류 격리를 확인한다."""

import pytest

from app.observability.measurements import ClientCall, MeasurementSinkRegistry, SellerRegionCut, ToolRun

_CALL = ClientCall(api="law", result="ok", seconds=0.2)


class _Recorder:
    def __init__(self) -> None:
        self.records: list = []

    def __call__(self, record) -> None:
        self.records.append(record)


def test_등록된_sink_전부에_기록을_넘긴다():
    registry, first, second = MeasurementSinkRegistry(), _Recorder(), _Recorder()
    registry.add(first)
    registry.add(second)

    registry.publish(_CALL)

    assert first.records == second.records == [_CALL]


def test_같은_sink를_두_번_등록해도_한_번만_받는다():
    registry, recorder = MeasurementSinkRegistry(), _Recorder()
    registry.add(recorder)
    registry.add(recorder)

    registry.publish(_CALL)

    assert len(recorder.records) == 1


def test_해제한_sink는_받지_않고_없는_sink_해제는_무시한다():
    registry, recorder = MeasurementSinkRegistry(), _Recorder()
    registry.add(recorder)

    registry.remove(recorder)
    registry.remove(recorder)
    registry.publish(_CALL)

    assert recorder.records == []


def test_임시_등록은_예외로_빠져나가도_해제된다():
    registry, recorder = MeasurementSinkRegistry(), _Recorder()

    with pytest.raises(RuntimeError), registry.added(recorder):
        raise RuntimeError
    registry.publish(_CALL)

    assert recorder.records == []


def test_sink_하나가_실패해도_나머지는_받고_기록한_쪽에_예외가_없다():
    registry, recorder = MeasurementSinkRegistry(), _Recorder()

    def broken(record):
        raise ValueError("boom")

    registry.add(broken)
    registry.add(recorder)
    records = [_CALL, ToolRun(tool_name="electrical_safety", status="failed", seconds=1.0, error_type="client"),
               SellerRegionCut(site="aliexpress", trimmed=False)]
    for record in records:
        registry.publish(record)

    assert recorder.records == records
