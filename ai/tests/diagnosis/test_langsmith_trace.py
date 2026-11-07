"""단계·Tool 호출이 LangSmith 이름으로 묶이는지 가짜 trace로 확인한다. 외부 전송 없음."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.diagnosis import langsmith_trace
from app.schemas.schemas import ToolName


class _Recorder:
    """langsmith.trace 대신 열린 이름과 끝낼 때 받은 값을 모은다."""

    def __init__(self) -> None:
        self.opened: list[dict] = []
        self.ended: list[dict] = []

    @contextmanager
    def __call__(self, name, run_type="chain", **kwargs):
        self.opened.append({"name": name, "run_type": run_type, **kwargs})
        yield SimpleNamespace(end=lambda **values: self.ended.append({"name": name, **values}))


@pytest.fixture
def recorder(monkeypatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(langsmith_trace, "trace", recorder)
    return recorder


@pytest.mark.parametrize(("retry_round", "name"), [(0, "verification"), (2, "verification #2")])
def test_단계는_회차가_구분되는_이름으로_묶고_결과를_돌려준다(recorder, retry_round, name):
    result = langsmith_trace.stage_hook("verification", retry_round, lambda: "결과")

    assert result == "결과"
    assert recorder.opened == [{"name": name, "run_type": "chain"}]
    assert recorder.ended == [{"name": name, "outputs": {"output": "결과"}}]


def test_Tool은_Tool_이름으로_묶는다(recorder):
    result = langsmith_trace.tool_hook(ToolName.LABEL_AD, lambda: "결과")

    assert result == "결과"
    assert recorder.opened == [{"name": "tool:labeling_advertising_detection", "run_type": "tool"}]


def test_단계_예외는_바꾸지_않고_그대로_올린다(recorder):
    error = ValueError("실패")

    def fail():
        raise error

    with pytest.raises(ValueError) as caught:
        langsmith_trace.stage_hook("selection", 0, fail)

    assert caught.value is error
    assert recorder.ended == []
