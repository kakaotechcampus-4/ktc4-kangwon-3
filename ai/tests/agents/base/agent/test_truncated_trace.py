"""잘린 응답의 LangSmith 기록: 상한 초과로 잘린 원문을 LangSmith 실행 안에서만 하위 실행으로 남긴다. 외부 전송 없음."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from openai import LengthFinishReasonError

from app.agents.base import agent as agent_module


class _Recorder:
    """langsmith trace 대신 열린 실행과 끝낼 때 받은 값을 모은다."""

    def __init__(self) -> None:
        self.opened: list[dict] = []
        self.ended: list[dict] = []

    @contextmanager
    def __call__(self, name, run_type="chain", **kwargs):
        self.opened.append({"name": name, "run_type": run_type, **kwargs})
        yield SimpleNamespace(end=lambda **values: self.ended.append(values))


@pytest.fixture
def recorder(monkeypatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(agent_module, "langsmith_trace", recorder)
    return recorder


def _in_langsmith_run(monkeypatch, inside: bool) -> None:
    monkeypatch.setattr(agent_module, "get_current_run_tree", lambda: object() if inside else None)


def test_LangSmith_실행_안에서는_잘린_원문을_하위_실행으로_남긴다(fakes, records, fake_gateway, recorder, monkeypatch):
    _in_langsmith_run(monkeypatch, inside=True)

    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(fake_gateway('{"value": "잘린', "length", [])).run(fakes.question)

    assert isinstance(caught.value.__cause__, LengthFinishReasonError)
    [opened] = recorder.opened
    assert opened["name"] == f"잘린 응답:{fakes.Agent.component_name}"
    assert opened["inputs"] == {"error_type": "LengthFinishReasonError"}
    [ended] = recorder.ended
    assert ended["outputs"]["raw"] == '{"value": "잘린'
    assert "output_tokens" in ended["outputs"]


def test_LangSmith_실행_밖에서는_기록하지_않는다(fakes, records, fake_gateway, recorder, monkeypatch):
    _in_langsmith_run(monkeypatch, inside=False)

    with pytest.raises(fakes.Error):
        fakes.Agent(fake_gateway('{"value": "잘린', "length", [])).run(fakes.question)

    assert recorder.opened == []


def test_기록에_실패해도_원래_실패를_그대로_올린다(fakes, records, fake_gateway, monkeypatch):
    _in_langsmith_run(monkeypatch, inside=True)

    def broken(*args, **kwargs):
        raise RuntimeError("LangSmith 기록 실패")

    monkeypatch.setattr(agent_module, "langsmith_trace", broken)

    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(fake_gateway('{"value": "잘린', "length", [])).run(fakes.question)

    assert isinstance(caught.value.__cause__, LengthFinishReasonError)
    assert records[-1]["error_type"] == "LengthFinishReasonError"
