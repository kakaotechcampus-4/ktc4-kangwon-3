"""더미 시나리오 표시를 입력에 남기고 다시 읽는지, 무작위 선택이 모든 값을 내는지 확인한다."""

import random

import pytest

from app.dummy import DummyFlow, DummyResult, DummyScenario, mark_scenario, random_scenario, read_scenario
from app.schemas.agent import ExtractionInput

_ITEM = ExtractionInput(product_id="p-1", text_blocks=["RC 보트"])


@pytest.mark.parametrize("flow", list(DummyFlow))
@pytest.mark.parametrize("result", list(DummyResult))
def test_남긴_시나리오를_그대로_읽는다(flow, result):
    scenario = DummyScenario(flow=flow, result=result)

    marked = mark_scenario(_ITEM, scenario)

    assert read_scenario(marked) == scenario
    assert marked.text_blocks[0] == "RC 보트"
    assert _ITEM.text_blocks == ["RC 보트"]


@pytest.mark.parametrize("blocks", [["RC 보트"], ["[dummy:flow=unknown,result=allowed]"]])
def test_표시가_없거나_값이_잘못되면_거절한다(blocks):
    with pytest.raises(ValueError):
        read_scenario(ExtractionInput(product_id="p-1", text_blocks=blocks))


def test_무작위_선택은_흐름과_결과를_모두_낸다():
    rng = random.Random(0)

    picked = [random_scenario(rng) for _ in range(200)]

    assert {scenario.flow for scenario in picked} == set(DummyFlow)
    assert {scenario.result for scenario in picked} == set(DummyResult)
