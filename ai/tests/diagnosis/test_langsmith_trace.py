"""단계·Tool 호출이 LangSmith 이름으로 묶이는지 가짜 trace로 확인한다. 외부 전송 없음."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.diagnosis import langsmith_trace
from app.domain.context import ExecutionContext, RunType
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


def test_진단은_상품_ID_이름으로_묶고_실행_정보를_남긴다(recorder):
    context = ExecutionContext(run_id="r1", product_id="p1", run_type=RunType.TEST, diagnosis_id="d1")
    calls = []

    def job(job_input, context, progress):
        calls.append((job_input, context, progress))
        return "결말"

    result = langsmith_trace.traced_job(job)("입력", context, "진행")

    assert result == "결말"
    assert calls == [("입력", context, "진행")]
    assert recorder.opened == [{
        "name": "diagnosis:p1", "run_type": "chain",
        "metadata": {"run_id": "r1", "run_type": "test", "diagnosis_id": "d1"},
    }]
    assert recorder.ended == [{"name": "diagnosis:p1", "outputs": {"output": "결말"}}]


@pytest.mark.parametrize(("value", "expected"), [(True, True), ("local", True), (False, False), (None, False)])
def test_켜짐_여부는_LangSmith_설정을_따른다(monkeypatch, value, expected):
    monkeypatch.setattr(langsmith_trace, "tracing_is_enabled", lambda: value)

    assert langsmith_trace.tracing_on() is expected
