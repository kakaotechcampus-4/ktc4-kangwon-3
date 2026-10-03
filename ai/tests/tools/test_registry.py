"""Tool 레지스트리 테스트. 각 Tool의 심사 로직이 아니라 등록 계약만 확인한다."""

import pytest

from app.schemas.schemas import ToolName
from app.tools.base import RegulatoryTool
from app.tools.registry import TOOL_REGISTRY


def test_6개_심사_도메인이_모두_등록되어_있다():
    assert set(TOOL_REGISTRY) == set(ToolName)


@pytest.mark.parametrize("name", list(ToolName))
def test_등록된_구현의_tool_name이_등록_키와_같다(name):
    tool_class = TOOL_REGISTRY[name]

    assert issubclass(tool_class, RegulatoryTool)
    assert tool_class.tool_name is name


@pytest.mark.parametrize("name", list(ToolName))
def test_등록된_구현은_인스턴스로_만들_수_있다(name):
    # 추상 메서드 execute를 구현하지 않으면 생성 단계에서 TypeError
    assert isinstance(TOOL_REGISTRY[name](), RegulatoryTool)
