"""PipelineManaged ToolExecutor의 최초 선택·실행·실패 경계를 검증한다."""

from collections.abc import Callable
from itertools import combinations

import pytest

from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import (
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)
from app.schemas.pipeline import RetryRequest
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


def test_최초_실행_결과는_선택_결정의_입력_순서와_무관하게_일정하다():
    selection = _selection()
    selection.decisions.reverse()

    result = ToolExecutor(_tools()).execute_initial(
        Product(product_id="p1"),
        selection,
    )

    assert [item.tool_name for item in result.tool_results] == list(ToolName)


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


def test_미선택_Tool을_재실행하면_최신_결과와_선택_상태를_갱신한다():
    tools = _tools()
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")

    # 최초에는 모든 Tool이 미선택 상태이다.
    initial_result = executor.execute_initial(product, _selection())
    original_result = initial_result.model_copy(deep=True)

    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )
    retry_request = RetryRequest(
        retry_round=1,
        requested_tools=[ToolName.RADIO],
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )

    result = executor.execute_retry(
        product,
        initial_result,
        retry_request,
    )

    radio_result = next(
        item for item in result.tool_results if item.tool_name is ToolName.RADIO
    )
    radio_decision = next(
        item
        for item in result.selection.decisions
        if item.tool_name is ToolName.RADIO
    )

    assert len(tools[ToolName.RADIO].calls) == 1
    assert all(
        len(tool.calls) == 0
        for name, tool in tools.items()
        if name is not ToolName.RADIO
    )

    assert radio_result.status is ToolStatus.SUCCESS
    assert radio_result.selected is True
    assert radio_result.retry_round == 1
    assert radio_decision.selected is True

    assert result.tool_result_history == [radio_result]

    # 재실행 함수가 입력 객체를 직접 변경하지 않아야 한다.
    assert initial_result == original_result


def test_기존_Tool을_재실행하면_최신_결과를_교체하고_이력을_누적한다():
    tools = _tools()
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")

    initial_result = executor.execute_initial(
        product,
        _selection(ToolName.ELECTRICAL),
    )
    original_result = initial_result.model_copy(deep=True)
    initial_electrical = next(
        item
        for item in initial_result.tool_results
        if item.tool_name is ToolName.ELECTRICAL
    )

    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.ELECTRICAL],
    )
    retry_request = RetryRequest(
        retry_round=1,
        requested_tools=[ToolName.ELECTRICAL],
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )

    result = executor.execute_retry(
        product,
        initial_result,
        retry_request,
    )

    latest_electrical = next(
        item
        for item in result.tool_results
        if item.tool_name is ToolName.ELECTRICAL
    )

    assert len(tools[ToolName.ELECTRICAL].calls) == 2
    assert latest_electrical.retry_round == 1
    assert latest_electrical.execution_id != initial_electrical.execution_id

    electrical_history = [
        item
        for item in result.tool_result_history
        if item.tool_name is ToolName.ELECTRICAL
    ]
    assert [item.retry_round for item in electrical_history] == [0, 1]
    assert electrical_history[0] == initial_electrical
    assert electrical_history[-1] == latest_electrical

    assert initial_result == original_result


def test_현재_Tool_결과와_다른_RetryRequest는_실행하지_않는다():
    tools = _tools()
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")

    initial_result = executor.execute_initial(product, _selection())

    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )
    retry_request = RetryRequest(
        retry_round=1,
        requested_tools=[ToolName.RADIO],
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )

    # RetryRequest 생성 이후 현재 결과가 변경된 상황을 만든다.
    current_result = initial_result.model_copy(deep=True)
    radio_result = next(
        item
        for item in current_result.tool_results
        if item.tool_name is ToolName.RADIO
    )
    radio_result.selection_reason = "RetryRequest 생성 이후 변경된 최신 결과"

    with pytest.raises(ValueError, match="현재 Tool 결과와 다릅니다"):
        executor.execute_retry(
            product,
            current_result,
            retry_request,
        )

    # 오래된 요청일 때 실제 Tool은 실행되지 않아야 한다.
    assert all(len(tool.calls) == 0 for tool in tools.values())


@pytest.mark.parametrize(
    "tool_name",
    list(ToolName),
    ids=lambda tool_name: tool_name.value,
)
def test_Tool_재실행_실패를_최신_결과와_이력으로_보존한다(tool_name):
    invocation_count = 0

    def succeed_then_fail(
        product: Product,
        decision: ToolSelectionItem,
    ) -> ToolResult:
        nonlocal invocation_count
        invocation_count += 1
        if invocation_count == 2:
            raise RuntimeError("외부 API 응답에 비밀번호가 포함됨")
        return _StubTool._success(product, decision)

    tools = _tools()
    tools[tool_name] = _StubTool(tool_name, succeed_then_fail)
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")

    initial_result = executor.execute_initial(product, _selection(tool_name))
    original_result = initial_result.model_copy(deep=True)
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[tool_name],
    )
    retry_request = RetryRequest(
        retry_round=1,
        requested_tools=[tool_name],
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )

    result = executor.execute_retry(product, initial_result, retry_request)

    latest_result = next(
        item for item in result.tool_results if item.tool_name is tool_name
    )
    tool_history = [
        item for item in result.tool_result_history if item.tool_name is tool_name
    ]

    assert latest_result.status is ToolStatus.FAILED
    assert latest_result.selected is True
    assert latest_result.retry_round == 1
    assert latest_result.execution_id is not None
    assert latest_result.error == "RuntimeError: Tool 실행에 실패했습니다."
    assert "비밀번호" not in latest_result.error

    assert [item.status for item in tool_history] == [
        ToolStatus.SUCCESS,
        ToolStatus.FAILED,
    ]
    assert [item.retry_round for item in tool_history] == [0, 1]
    assert tool_history[-1] == latest_result
    assert len(tools[tool_name].calls) == 2
    assert all(
        len(tool.calls) == 0
        for name, tool in tools.items()
        if name is not tool_name
    )

    # 재실행 실패 후에도 입력 객체는 변경하지 않는다.
    assert initial_result == original_result


@pytest.mark.parametrize(
    "requested_tools",
    list(combinations(ToolName, 2)),
    ids=lambda tools: "-".join(tool.value for tool in tools),
)
def test_여러_Tool_재실행은_요청된_결과만_교체한다(requested_tools):
    tools = _tools()
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")
    selection = _selection()
    selection.decisions.reverse()
    initial_result = executor.execute_initial(product, selection)
    initial_by_name = {
        item.tool_name: item.model_copy(deep=True)
        for item in initial_result.tool_results
    }
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=list(requested_tools),
    )
    retry_request = RetryRequest(
        retry_round=1,
        requested_tools=list(requested_tools),
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )

    result = executor.execute_retry(product, initial_result, retry_request)

    result_by_name = {item.tool_name: item for item in result.tool_results}
    requested_set = set(requested_tools)
    for tool_name in ToolName:
        if tool_name in requested_set:
            assert len(tools[tool_name].calls) == 1
            assert result_by_name[tool_name].status is ToolStatus.SUCCESS
            assert result_by_name[tool_name].retry_round == 1
        else:
            assert tools[tool_name].calls == []
            assert result_by_name[tool_name] == initial_by_name[tool_name]

    assert [item.tool_name for item in result.tool_result_history] == [
        tool_name
        for tool_name in ToolName
        if tool_name in requested_set
    ]


@pytest.mark.parametrize(
    "tool_name",
    list(ToolName),
    ids=lambda tool_name: tool_name.value,
)
def test_재실행_결과를_다음_회차_입력으로_연결한다(tool_name):
    tools = _tools()
    executor = ToolExecutor(tools)
    product = Product(product_id="p1")
    initial_result = executor.execute_initial(product, _selection(tool_name))
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[tool_name],
    )
    first_request = RetryRequest(
        retry_round=1,
        requested_tools=[tool_name],
        verification=verification,
        latest_tool_results=initial_result.tool_results,
    )
    first_retry = executor.execute_retry(product, initial_result, first_request)
    first_retry_snapshot = first_retry.model_copy(deep=True)
    second_request = RetryRequest(
        retry_round=2,
        requested_tools=[tool_name],
        verification=verification,
        latest_tool_results=first_retry.tool_results,
    )

    second_retry = executor.execute_retry(product, first_retry, second_request)

    latest_result = next(
        item for item in second_retry.tool_results if item.tool_name is tool_name
    )
    tool_history = [
        item
        for item in second_retry.tool_result_history
        if item.tool_name is tool_name
    ]
    assert latest_result.retry_round == 2
    assert [item.retry_round for item in tool_history] == [0, 1, 2]
    assert len({item.execution_id for item in tool_history}) == 3
    assert len(tools[tool_name].calls) == 3
    assert first_retry == first_retry_snapshot
