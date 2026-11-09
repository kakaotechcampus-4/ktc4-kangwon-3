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


@pytest.mark.parametrize("name", list(ToolName))
def test_등록된_구현은_선택된_경우의_실행을_구현한다(name):
    # RegulatoryTool._run은 추상 메서드가 아니라 구현을 빠뜨려도 생성은 됨. 등록된 Tool은 여기서 막음
    assert TOOL_REGISTRY[name]._run is not RegulatoryTool._run


def test_등록된_모든_Tool은_모델_프로필이_있다():
    # 프로필이 없으면 모델을 주입하지 않은 실제 실행에서 build_tool_model이 ConfigError를 낸다.
    # 테스트는 대부분 가짜 모델을 넣어 이 경로를 지나지 않으므로 여기서 따로 막는다.
    from app.config import TOOL_PROFILES

    assert {name.value for name in TOOL_REGISTRY} <= set(TOOL_PROFILES)


# 정보 부족 카드의 둘째 문장(화면의 판단 근거). 어떤 상품일 때 무엇을 확인해야 하는지 분야마다 적는다
INSUFFICIENT_GUIDES = {
    ToolName.CUSTOMS: "통관 때 필요한 서류가 있는지는 관세사나 세관에 직접 확인이 필요합니다.",
    ToolName.RADIO: "블루투스, Wi-Fi 같은 무선 기능이 있는 상품이라면 전파 인증 대상인지 직접 확인이 필요합니다.",
    ToolName.FOOD_DRUG: "음식에 닿거나, 먹거나, 몸에 바르는 상품이라면 직접 확인이 필요합니다.",
    ToolName.ELECTRICAL: "전기를 쓰는 상품이라면 KC 인증 대상인지 직접 확인이 필요합니다.",
    ToolName.CHILDREN: "만 13세 이하 어린이가 쓰는 상품이라면 KC 인증 대상인지 직접 확인이 필요합니다.",
}


@pytest.mark.parametrize("name", list(INSUFFICIENT_GUIDES))
def test_정보_부족_카드는_어떤_상품이면_직접_확인해야_하는지_알려_준다(name):
    _, summary, rationale = TOOL_REGISTRY[name].insufficient

    assert rationale == INSUFFICIENT_GUIDES[name]
    # 본문이 이미 "판단하지 못했습니다"로 끝나므로 같은 말을 되풀이하지 않고, 겹친 부정문도 쓰지 않음
    assert summary.endswith("판단하지 못했습니다.")
    assert "보류" not in rationale and "보지는 않습니다" not in rationale
