"""에이전트 입출력 스키마: ToolSelectionResponse는 6개 Tool을 정확히 한 번씩."""

import pytest

from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.schemas import ToolName


def _item(name: ToolName) -> ToolSelectionItem:
    return ToolSelectionItem(tool_name=name, selected=False, reason="판단")


def test_ToolSelectionResponse는_6개_Tool을_한_번씩_받는다():
    assert len(ToolSelectionResponse(decisions=[_item(name) for name in ToolName]).decisions) == 6


def test_ToolSelectionResponse는_6개_미만이면_거부한다():
    with pytest.raises(ValueError, match="6개 심사 툴"):
        ToolSelectionResponse(decisions=[_item(ToolName.CUSTOMS)])


def test_ToolSelectionResponse는_중복_Tool을_거부한다():
    # 개수는 6개지만 통관이 두 번, 표시광고가 빠짐
    names = [ToolName.CUSTOMS, ToolName.CUSTOMS, ToolName.RADIO, ToolName.FOOD_DRUG, ToolName.ELECTRICAL, ToolName.CHILDREN]

    with pytest.raises(ValueError, match="6개 심사 툴"):
        ToolSelectionResponse(decisions=[_item(name) for name in names])
