"""단계 다시 실행 설정: 이전 trace에서 첫 회차 단계 결과·실행 입력 읽기, 건너뛸 단계, 하나만 돌리고 멈춤을 확인한다."""

import pytest

from app.diagnosis.replay import (
    ReplayError, ReplaySkipHook, ReplayStopHook, ReplayStopped, StageReplay, replay_input,
)
from app.observability.trace import trace_run, trace_step
from app.schemas.agent import ExtractionInput
from app.schemas.product import Product
from app.schemas.session import DiagnosisInput

JOB_INPUT = DiagnosisInput(source=ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"]))


def _trace(*steps):
    return {"steps": list(steps)}


EXTRACTION = {"id": "s1", "kind": "extraction", "input": JOB_INPUT.model_dump(mode="json"),
              "output": Product(product_id="p-1").model_dump(mode="json")}


def test_시작_단계_앞_단계는_저장한_결과를_모델로_돌려주고_시작_단계부터는_None():
    replay = StageReplay.from_trace(_trace(EXTRACTION), "selection")

    assert replay.saved("extraction") == Product(product_id="p-1")
    assert replay.saved("selection") is None
    assert replay.saved("verification") is None


def test_재실행_회차_결과는_다시_실행에_쓰지_않는다():
    retried = {"id": "s9", "kind": "aggregation", "round": 1, "output": {"x": 1}}

    with pytest.raises(ReplayError, match="selection, tool_execution, aggregation"):
        StageReplay.from_trace(_trace(EXTRACTION, retried), "verification")


@pytest.mark.parametrize(("trace", "stage", "message"), [
    (_trace(EXTRACTION), "packing", "모르는 단계"),
    (_trace(), "selection", "extraction"),
])
def test_다시_실행할_수_없는_trace는_오류(trace, stage, message):
    with pytest.raises(ReplayError, match=message):
        StageReplay.from_trace(trace, stage)


def test_저장한_결과가_지금_스키마와_다르면_오류():
    broken = {**EXTRACTION, "output": {"product_id": "p-1", "없는_필드": 1}}

    with pytest.raises(ReplayError, match="extraction 결과"):
        StageReplay.from_trace(_trace(broken), "selection").saved("extraction")


def test_하나만_돌리는_설정은_시작_단계를_마치면_결말을_남기고_멈춘다(tmp_path):
    replay = StageReplay.from_trace(_trace(EXTRACTION), "selection", only=True)

    with trace_run(tmp_path) as recorder:
        replay.done("extraction")
        with pytest.raises(ReplayStopped):
            replay.done("selection")

    assert recorder.finish == {"reason": "stopped", "stage": "selection"}


def test_건너뛰기_hook은_첫_회차_시작_단계_앞만_저장한_결과로_바꾸고_replayed를_남긴다(tmp_path):
    hook = ReplaySkipHook(StageReplay.from_trace(_trace(EXTRACTION), "selection"))
    calls = []

    with trace_run(tmp_path) as recorder:
        with trace_step("extraction"):
            saved = hook("extraction", 0, lambda: calls.append("extraction"))
        with trace_step("selection"):
            hook("selection", 0, lambda: calls.append("selection"))

    assert saved == Product(product_id="p-1")
    assert calls == ["selection"]
    assert [step.get("replayed") for step in recorder.steps] == [True, None]


def test_건너뛰기_hook은_재실행_회차엔_실제로_부른다():
    hook = ReplaySkipHook(StageReplay.from_trace(_trace(EXTRACTION), "selection"))

    assert hook("extraction", 1, lambda: "실제") == "실제"


def test_멈춤_hook은_시작_단계를_마친_뒤에_멈추고_재실행_회차엔_멈추지_않는다(tmp_path):
    hook = ReplayStopHook(StageReplay.from_trace(_trace(EXTRACTION), "selection", only=True))
    calls = []

    with trace_run(tmp_path) as recorder:
        assert hook("selection", 1, lambda: "재실행") == "재실행"
        with pytest.raises(ReplayStopped):
            hook("selection", 0, lambda: calls.append("selection"))

    # 단계는 끝까지 돈 뒤 멈춤
    assert calls == ["selection"]
    assert recorder.finish == {"reason": "stopped", "stage": "selection"}


def test_실행_입력은_추출_단계_input에서_읽는다():
    assert replay_input(_trace(EXTRACTION)) == JOB_INPUT

    with pytest.raises(ReplayError, match="실행 입력"):
        replay_input(_trace())
