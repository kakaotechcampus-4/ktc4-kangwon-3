"""Tool 레지스트리 테스트. 각 Tool의 심사 로직이 아니라 등록 계약만 확인한다."""

import inspect

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
def test_등록된_구현에_구현하지_않은_추상_메서드가_없다(name):
    # 조회 객체는 생성자 필수 인자라 인자 없이 만들지 않음. 조립은 파이프라인 연결 때
    assert not inspect.isabstract(TOOL_REGISTRY[name])


def test_등록된_모든_Tool은_모델_프로필이_있다():
    # 프로필이 없으면 모델을 주입하지 않은 실제 실행에서 build_tool_model이 ConfigError를 낸다.
    # 테스트는 대부분 가짜 모델을 넣어 이 경로를 지나지 않으므로 여기서 따로 막는다.
    from app.config import TOOL_PROFILES

    assert {name.value for name in TOOL_REGISTRY} <= set(TOOL_PROFILES)
