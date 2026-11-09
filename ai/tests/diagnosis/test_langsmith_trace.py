"""단계·Tool 호출이 LangSmith 이름으로 묶이고 진단 입력이 Input에 남는지 가짜 trace로 확인한다. 외부 전송 없음."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.diagnosis import langsmith_trace
from app.domain.context import ExecutionContext, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.schemas import ToolName
from app.schemas.session import DiagnosisInput, SessionAnswer


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


def test_진단은_상품_ID_이름으로_묶고_진단_입력과_실행_정보를_남긴다(recorder):
    context = ExecutionContext(run_id="r1", product_id="p1", run_type=RunType.TEST, diagnosis_id="d1")
    job_input = DiagnosisInput(source=ExtractionInput(product_id="p1", text_blocks=["보조배터리"]))
    calls = []

    def job(job_input, context, progress):
        calls.append((job_input, context, progress))
        return "결말"

    result = langsmith_trace.traced_job(job)(job_input, context, "진행")

    assert result == "결말"
    assert calls == [(job_input, context, "진행")]
    # 예전에는 Input 없이 열어 LangSmith 화면의 진단 Input이 비어 있었음 (#746)
    assert recorder.opened == [{
        "name": "diagnosis:p1", "run_type": "chain",
        "inputs": {"product_id": "p1", "source_url": None, "text_blocks": ["보조배터리"], "image_urls": [],
                   "resume": False, "answers": []},
        "metadata": {"run_id": "r1", "run_type": "test", "diagnosis_id": "d1"},
    }]
    assert recorder.ended == [{"name": "diagnosis:p1", "outputs": {"output": "결말"}}]


def test_재진단이면_답변과_재진단_여부를_남기고_이전_결과_본문은_넣지_않는다():
    job_input = DiagnosisInput(
        source=ExtractionInput(product_id="p1", source_url="https://seller.example/item"),
        previous=build_dummy_assessment("p1"),
        answers=[SessionAnswer(question_round=1, question_key="battery_capacity", answer_text="10000mAh")],
    )

    inputs = langsmith_trace.diagnosis_inputs(job_input)

    assert inputs["resume"] is True
    assert inputs["answers"] == [{"question_round": 1, "question_key": "battery_capacity", "answer_text": "10000mAh"}]
    assert "previous" not in inputs
    assert inputs["source_url"] == "https://seller.example/item"


def test_base64_이미지는_앞부분과_길이만_남기고_주소는_그대로_남긴다():
    data_uri = "data:image/png;base64," + "A" * 200_000
    job_input = DiagnosisInput(source=ExtractionInput(product_id="p1", image_urls=["https://s3/a.png", data_uri]))

    [url, short] = langsmith_trace.diagnosis_inputs(job_input)["image_urls"]

    assert url == "https://s3/a.png"
    assert short == f"{data_uri[:langsmith_trace.DATA_URI_PREFIX]}… (200,022자)"


@pytest.mark.parametrize(("value", "expected"), [(True, True), ("local", True), (False, False), (None, False)])
def test_켜짐_여부는_LangSmith_설정을_따른다(monkeypatch, value, expected):
    monkeypatch.setattr(langsmith_trace, "tracing_is_enabled", lambda: value)

    assert langsmith_trace.tracing_on() is expected
