"""판단 선택 문턱값: 판단 모델·Tool마다 빠짐없이 있는지, 없는 조합은 막는지."""

import pytest

from app.agents.decision_selection.questions import TOOL_QUESTIONS
from app.agents.decision_selection.thresholds import THRESHOLDS, threshold
from app.config import DECISION_MODELS
from app.schemas.schemas import ToolName


def test_판단_모델마다_질문_있는_Tool의_문턱값이_다_있다():
    assert set(THRESHOLDS) == set(DECISION_MODELS)
    assert all(set(values) == set(TOOL_QUESTIONS) for values in THRESHOLDS.values())


def test_문턱값은_0과_1_사이다():
    assert all(0 < value < 1 for values in THRESHOLDS.values() for value in values.values())


def test_모델과_Tool로_문턱값을_찾는다():
    assert threshold("typesafe/jev-latest", ToolName.CHILDREN) == 0.3


@pytest.mark.parametrize(("model", "tool"), [
    ("unknown/model", ToolName.CHILDREN),
    ("typesafe/jev-latest", ToolName.CUSTOMS),
])
def test_정해지지_않은_조합은_막는다(model, tool):
    with pytest.raises(ValueError, match="문턱값이 정해지지 않았습니다"):
        threshold(model, tool)
