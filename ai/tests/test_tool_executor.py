"""PipelineManaged ToolExecutor의 최초 선택·실행·실패 경계를 검증한다."""

from collections.abc import Callable

import pytest

from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import ToolName, ToolResult, ToolStatus
from app.tools.base import RegulatoryTool
from app.pipeline.tool_executor import ToolExecutor


class _StubTool(RegulatoryTool):
    def __init__(
        self,
        name: ToolName,
        behavior: Callable[[Product, ToolSelectionItem], ToolResult] | None = None,
    ) -> None:
        self.tool_name = name
        self.calls: list[tuple[Product, ToolSelectionItem]] = []
        self._behavior = behavior or self._success

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        self.calls.append((product, decision))
        return self._behavior(product, decision)

    @staticmethod
    def _success(product: Product, decision: ToolSelectionItem) -> ToolResult:
        return ToolResult(
            tool_name=decision.tool_name,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="Tool이 만든 이유",
        )


def _tools() -> dict[ToolName, _StubTool]:
    return {name: _StubTool(name) for name in ToolName}


def _selection(*selected_tools: ToolName) -> ToolSelectionResponse:
    selected = set(selected_tools)
    return ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(
                tool_name=name,
                selected=name in selected,
                reason=f"{name.value} 심사 선택 이유",
            )
            for name in ToolName
        ]
    )


def test_6개_Tool이_모두_등록되지_않으면_실패한다():
    tools = _tools()
    tools.pop(ToolName.RADIO)

    with pytest.raises(ValueError, match="6개"):
        ToolExecutor(tools)


def test_레지스트리_키와_Tool의_이름이_다르면_실패한다():
    tools = _tools()
    tools[ToolName.RADIO] = _StubTool(ToolName.CUSTOMS)

    with pytest.raises(ValueError, match="tool_name"):
        ToolExecutor(tools)


def test_최초_실행은_최신_결과_6개와_실제_실행_이력을_만든다():
    tools = _tools()
    selection = _selection(ToolName.CUSTOMS, ToolName.ELECTRICAL)

    result = ToolExecutor(tools).execute_initial(Product(product_id="p1"), selection)

    assert result.selection == selection
    assert result.selection is not selection
    assert len(result.tool_results) == len(ToolName)
    assert [item.tool_name for item in result.tool_results] == list(ToolName)
    assert len(result.tool_result_history) == 2
    assert {item.tool_name for item in result.tool_result_history} == {
        ToolName.CUSTOMS,
        ToolName.ELECTRICAL,
    }
    assert all(item.status is not ToolStatus.SKIPPED for item in result.tool_result_history)


def test_미선택_Tool은_실행하지_않고_skipped로_기록한다():
    tools = _tools()
    selection = _selection(ToolName.ELECTRICAL)

    result = ToolExecutor(tools).execute_initial(Product(product_id="p1"), selection)

    radio_result = next(
        item for item in result.tool_results if item.tool_name is ToolName.RADIO
    )
    radio_decision = next(
        item for item in selection.decisions if item.tool_name is ToolName.RADIO
    )
    assert tools[ToolName.RADIO].calls == []
    assert radio_result.status is ToolStatus.SKIPPED
    assert radio_result.selected is False
    assert radio_result.execution_id is None
    assert radio_result.retry_round == 0
    assert radio_result.selection_reason == radio_decision.reason


def test_선택_Tool에_복사본을_전달하고_실행_정보를_부여한다():
    tools = _tools()
    product = Product(product_id="p1", product_name="무선 이어폰")
    selection = _selection(ToolName.ELECTRICAL)
    decision = next(
        item for item in selection.decisions if item.tool_name is ToolName.ELECTRICAL
    )

    result = ToolExecutor(tools).execute_initial(product, selection)

    received_product, received_decision = tools[ToolName.ELECTRICAL].calls[0]
    electrical_result = next(
        item for item in result.tool_results if item.tool_name is ToolName.ELECTRICAL
    )
    assert received_product == product
    assert received_product is not product
    assert received_decision == decision
    assert received_decision is not decision
    assert electrical_result.status is ToolStatus.SUCCESS
    assert electrical_result.execution_id is not None
    assert electrical_result.retry_round == 0
    assert electrical_result.selection_reason == decision.reason


def test_Tool이_전달받은_복사본을_변경해도_원본은_변하지_않는다():
    def mutate(product: Product, decision: ToolSelectionItem) -> ToolResult:
        product.product_name = "변경됨"
        decision.reason = "변경됨"
        return _StubTool._success(product, decision)

    tools = _tools()
    tools[ToolName.ELECTRICAL] = _StubTool(ToolName.ELECTRICAL, mutate)
    product = Product(product_id="p1", product_name="원본")
    selection = _selection(ToolName.ELECTRICAL)

    ToolExecutor(tools).execute_initial(product, selection)

    decision = next(
        item for item in selection.decisions if item.tool_name is ToolName.ELECTRICAL
    )
    assert product.product_name == "원본"
    assert decision.reason == "electrical_safety 심사 선택 이유"


def test_Tool_예외는_실패_결과와_실행_이력으로_보존한다():
    def fail(product: Product, decision: ToolSelectionItem) -> ToolResult:
        raise RuntimeError("외부 API 응답에 비밀번호가 포함됨")

    tools = _tools()
    tools[ToolName.ELECTRICAL] = _StubTool(ToolName.ELECTRICAL, fail)

    result = ToolExecutor(tools).execute_initial(
        Product(product_id="p1"),
        _selection(ToolName.ELECTRICAL),
    )

    electrical_result = next(
        item for item in result.tool_results if item.tool_name is ToolName.ELECTRICAL
    )
    assert electrical_result.status is ToolStatus.FAILED
    assert electrical_result.selected is True
    assert electrical_result.execution_id is not None
    assert electrical_result.error == "RuntimeError: Tool 실행에 실패했습니다."
    assert "비밀번호" not in electrical_result.error
    assert result.tool_result_history == [electrical_result]


def test_Tool_하나가_실패해도_다음_선택_Tool을_계속_실행한다():
    def fail(product: Product, decision: ToolSelectionItem) -> ToolResult:
        raise RuntimeError("실행 실패")

    tools = _tools()
    tools[ToolName.ELECTRICAL] = _StubTool(ToolName.ELECTRICAL, fail)

    result = ToolExecutor(tools).execute_initial(
        Product(product_id="p1"),
        _selection(ToolName.ELECTRICAL, ToolName.CHILDREN),
    )

    statuses = {item.tool_name: item.status for item in result.tool_results}
    assert statuses[ToolName.ELECTRICAL] is ToolStatus.FAILED
    assert statuses[ToolName.CHILDREN] is ToolStatus.SUCCESS
    assert len(tools[ToolName.CHILDREN].calls) == 1
    assert [item.tool_name for item in result.tool_result_history] == [
        ToolName.ELECTRICAL,
        ToolName.CHILDREN,
    ]


@pytest.mark.parametrize(
    "invalid_result",
    [
        ToolResult(
            tool_name=ToolName.RADIO,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="다른 Tool 결과",
        ),
        ToolResult(
            tool_name=ToolName.ELECTRICAL,
            status=ToolStatus.SKIPPED,
            selected=False,
            selection_reason="잘못된 미선택 결과",
        ),
    ],
)
def test_선택_Tool의_식별_정보가_다르면_실패_결과로_변환한다(invalid_result):
    tools = _tools()
    tools[ToolName.ELECTRICAL] = _StubTool(
        ToolName.ELECTRICAL,
        lambda product, decision: invalid_result,
    )

    result = ToolExecutor(tools).execute_initial(
        Product(product_id="p1"),
        _selection(ToolName.ELECTRICAL),
    )

    electrical_result = next(
        item for item in result.tool_results if item.tool_name is ToolName.ELECTRICAL
    )
    assert electrical_result.status is ToolStatus.FAILED
    assert electrical_result.selected is True
    assert electrical_result.error == "ValueError: Tool 실행에 실패했습니다."
