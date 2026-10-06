"""심사 Tool을 LangChain 툴로 감싸는 래퍼 테스트. 가짜 구현으로 계약만 확인한다."""

import json

import pytest
from langchain_core.messages import ToolMessage

from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import ToolName, ToolResult, ToolStatus
from app.tools.base import RegulatoryTool
from app.tools.langchain_tools import TOOL_DESCRIPTIONS, build_langchain_tools


class _FakeTool(RegulatoryTool):
    """받은 상품·결정을 기록하고, 지정한 이름으로 성공 결과를 돌려준다."""

    def __init__(self, name: ToolName, *, result_name: ToolName | None = None, selected: bool = True):
        self.tool_name = name
        self._result_name = result_name or name
        self._selected = selected
        self.calls: list[tuple[str | None, ToolSelectionItem]] = []

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        self.calls.append((product.product_name, decision))
        # 호출마다 상품 사본을 받는지 확인하기 위해 받은 상품을 바꿔 봄
        product.product_name = "구현이 바꾼 이름"
        return ToolResult(
            tool_name=self._result_name,
            status=ToolStatus.SUCCESS,
            selected=self._selected,
            selection_reason=decision.reason,
            raw_response={"secret": "원본 응답"},
        )


def _implementations(**overrides: _FakeTool) -> dict[ToolName, _FakeTool]:
    impls = {name: _FakeTool(name) for name in ToolName}
    impls.update({ToolName(key): value for key, value in overrides.items()})
    return impls


def _call(tool, reason: str) -> ToolMessage:
    return tool.invoke({"type": "tool_call", "id": "call-1", "name": tool.name, "args": {"reason": reason}})


def test_6개_툴을_도메인_이름과_설명으로_만든다():
    tools = build_langchain_tools(Product(product_id="p-1"), _implementations())

    assert [t.name for t in tools] == [name.value for name in ToolName]
    assert all(t.description == TOOL_DESCRIPTIONS[ToolName(t.name)] for t in tools)


def test_구현이_하나라도_빠지면_만들지_않는다():
    impls = _implementations()
    del impls[ToolName.RADIO]

    with pytest.raises(ValueError, match="6개"):
        build_langchain_tools(Product(product_id="p-1"), impls)


def test_등록_이름과_구현의_tool_name이_다르면_만들지_않는다():
    impls = _implementations(radio_compliance=_FakeTool(ToolName.CUSTOMS))

    with pytest.raises(ValueError, match="일치하지 않습니다"):
        build_langchain_tools(Product(product_id="p-1"), impls)


def test_호출하면_LLM에는_원본_응답을_뺀_내용을_실행부에는_ToolResult를_준다():
    tool = build_langchain_tools(Product(product_id="p-1"), _implementations())[0]

    message = _call(tool, "무선 충전 기능이 있음")

    assert isinstance(message.artifact, ToolResult)
    assert message.artifact.selection_reason == "무선 충전 기능이 있음"
    content = json.loads(message.content)
    assert "raw_response" not in content
    assert content["tool_name"] == tool.name


def test_구현은_선택된_결정과_원래_상품의_사본을_받는다():
    impls = _implementations()
    product = Product(product_id="p-1", product_name="휴대용 선풍기")
    tool = build_langchain_tools(product, impls)[0]

    _call(tool, "첫 번째 호출")
    _call(tool, "두 번째 호출")

    calls = impls[ToolName(tool.name)].calls
    assert all(decision.selected and decision.tool_name.value == tool.name for _, decision in calls)
    # 구현이 상품을 바꿔도 다음 호출과 원래 상품에는 영향 없음
    assert [received_name for received_name, _ in calls] == ["휴대용 선풍기", "휴대용 선풍기"]
    assert product.product_name == "휴대용 선풍기"


@pytest.mark.parametrize(
    "fake",
    [
        _FakeTool(ToolName.CUSTOMS, result_name=ToolName.RADIO),  # 다른 툴 이름의 결과
        _FakeTool(ToolName.CUSTOMS, selected=False),               # 미선택 결과
    ],
)
def test_결과의_식별_정보가_다르면_성공으로_넘기지_않는다(fake):
    tool = build_langchain_tools(Product(product_id="p-1"), _implementations(customs_requirements=fake))[0]

    with pytest.raises(ValueError, match="식별 정보"):
        _call(tool, "통관 확인")
