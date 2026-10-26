"""RegulatoryTool.execute: 선택 확인·SKIPPED는 공통 처리하고, 선택된 경우만 _run을 부름."""

import pytest

from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import ToolName, ToolResult, ToolStatus
from app.tools.base import RegulatoryTool

PRODUCT = Product(product_id="p-1")


class _Tool(RegulatoryTool):
    tool_name = ToolName.RADIO

    def __init__(self):
        self.calls: list[Product] = []

    def _run(self, product, decision):
        self.calls.append(product)
        return ToolResult(tool_name=self.tool_name, selected=True, selection_reason=decision.reason,
                          status=ToolStatus.SUCCESS)


def _decision(selected=True, tool_name=ToolName.RADIO):
    return ToolSelectionItem(tool_name=tool_name, selected=selected, reason="무선 기능")


def test_선택되면_run을_부른다():
    tool = _Tool()

    result = tool.execute(PRODUCT, _decision())

    assert tool.calls == [PRODUCT]
    assert result.status is ToolStatus.SUCCESS


def test_미선택이면_run_없이_SKIPPED와_선택_이유를_돌려준다():
    tool = _Tool()

    result = tool.execute(PRODUCT, _decision(selected=False))

    assert tool.calls == []
    assert (result.status, result.selected, result.selection_reason) == (ToolStatus.SKIPPED, False, "무선 기능")


def test_다른_Tool의_선택_결정이면_ValueError():
    with pytest.raises(ValueError, match="이름"):
        _Tool().execute(PRODUCT, _decision(tool_name=ToolName.CUSTOMS))
