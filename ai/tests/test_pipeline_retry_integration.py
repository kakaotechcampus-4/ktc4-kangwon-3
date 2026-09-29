"""실제 Pipeline 구성 요소를 연결해 Tool 재실행 정책을 검증한다."""

from collections.abc import Callable

import pytest

from app.agents.verification import VerificationAgent
from app.pipeline.aggregator import ResultAggregator
from app.pipeline.runner import CompliancePipeline
from app.pipeline.tool_executor import ToolExecutor
from app.schemas.agent import (
    ExtractionInput,
    ToolSelectionItem,
    ToolSelectionResponse,
)
from app.schemas.pipeline import RetryRequest, SelectionResult
from app.schemas.product import Product
from app.schemas.schemas import (
    AdvertisingAssessment,
    ChildrenAssessment,
    CustomsAssessment,
    Determination,
    DraftAssessment,
    ElectricalAssessment,
    FinalVerificationStatus,
    FoodDrugAssessment,
    LegalSource,
    OverallStatus,
    RadioAssessment,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolAssessment,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)
from app.tools.base import RegulatoryTool


class _StubTool(RegulatoryTool):
    def __init__(
        self,
        name: ToolName,
        behavior: Callable[[Product, ToolSelectionItem], ToolResult],
    ) -> None:
        self.tool_name = name
        self.calls = 0
        self._behavior = behavior

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        self.calls += 1
        return self._behavior(product, decision)


class _FakeExtractor:
    def __init__(self, product: Product) -> None:
        self._product = product

    def extract(self, source: ExtractionInput) -> Product:
        assert source.product_id == self._product.product_id
        return self._product.model_copy(deep=True)


class _FakeSelector:
    def __init__(self, selected_tool: ToolName) -> None:
        self._selected_tool = selected_tool

    def select(self, product: Product) -> ToolSelectionResponse:
        return ToolSelectionResponse(
            decisions=[
                ToolSelectionItem(
                    tool_name=name,
                    selected=name is self._selected_tool,
                    reason=(
                        "규제 검토 대상"
                        if name is self._selected_tool
                        else "검토 신호 없음"
                    ),
                )
                for name in ToolName
            ]
        )


class _TrackingToolExecutor:
    """실제 실행기에 위임하고 마지막 선택 결과만 테스트에서 관찰한다."""

    def __init__(self, delegate: ToolExecutor) -> None:
        self._delegate = delegate
        self.latest_result: SelectionResult | None = None

    def execute_initial(
        self,
        product: Product,
        selection: ToolSelectionResponse,
    ) -> SelectionResult:
        self.latest_result = self._delegate.execute_initial(product, selection)
        return self.latest_result

    def execute_retry(
        self,
        product: Product,
        selection_result: SelectionResult,
        retry_request: RetryRequest,
    ) -> SelectionResult:
        self.latest_result = self._delegate.execute_retry(
            product,
            selection_result,
            retry_request,
        )
        return self.latest_result


class _RuleOnlyVerifier:
    """외부 모델 호출 없이 실제 Verification 규칙을 Pipeline에 연결한다."""

    def __init__(self) -> None:
        self._delegate = VerificationAgent()

    def verify(self, draft: DraftAssessment) -> VerificationResult:
        return self._delegate.verify_rules(draft)


def _unused_tool_result(
    product: Product,
    decision: ToolSelectionItem,
) -> ToolResult:
    raise AssertionError(f"미선택 Tool이 실행되었습니다: {decision.tool_name}")


def _assessment_for(tool_name: ToolName) -> ToolAssessment:
    return {
        ToolName.CUSTOMS: CustomsAssessment(),
        ToolName.RADIO: RadioAssessment(),
        ToolName.FOOD_DRUG: FoodDrugAssessment(),
        ToolName.ELECTRICAL: ElectricalAssessment(),
        ToolName.CHILDREN: ChildrenAssessment(),
        ToolName.LABEL_AD: AdvertisingAssessment(overall_risk=RiskLevel.LOW),
    }[tool_name]


@pytest.mark.parametrize("selected_tool", list(ToolName))
def test_Tool_재실행이_실패하면_지적된_판단만_제외하고_유효한_판단은_보존한다(
    selected_tool: ToolName,
):
    challenged_finding = RegulatoryFinding(
        tool_name=selected_tool,
        subject="규제 적용 검토",
        determination=Determination.REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        summary="규제 검토가 필요합니다.",
        rationale="규제 대상 특성이 확인되었습니다.",
    )
    valid_high_risk_finding = RegulatoryFinding(
        tool_name=selected_tool,
        subject="확인된 고위험 규제",
        determination=Determination.REQUIRED,
        risk_level=RiskLevel.HIGH,
        summary="법령 근거가 확인된 고위험 판단입니다.",
        rationale="실제 기관 자료에서 적용 요건을 확인했습니다.",
        legal_sources=[
            LegalSource(
                source_name="국가기관",
                quoted_text="해당 상품은 규제 요건을 준수해야 한다.",
                source_url="https://example.go.kr/law",
                is_mock=False,
            )
        ],
    )
    warning_finding = RegulatoryFinding(
        tool_name=selected_tool,
        subject="mock 근거가 있는 고위험 규제",
        determination=Determination.REQUIRED,
        risk_level=RiskLevel.HIGH,
        summary="실자료 확인 전까지 경고로 유지할 판단입니다.",
        rationale="예시 자료에서 적용 가능성을 확인했습니다.",
        legal_sources=[
            LegalSource(
                source_name="예시 기관",
                quoted_text="해당 상품은 규제 대상일 수 있다.",
                source_url="https://example.test/law",
            )
        ],
    )

    def selected_tool_behavior(
        product: Product,
        decision: ToolSelectionItem,
    ) -> ToolResult:
        if selected_tool_impl.calls == 1:
            return ToolResult(
                tool_name=selected_tool,
                status=ToolStatus.SUCCESS,
                selected=True,
                selection_reason=decision.reason,
                query={"product_id": product.product_id},
                result=_assessment_for(selected_tool),
                findings=[
                    challenged_finding,
                    valid_high_risk_finding,
                    warning_finding,
                ],
                required_actions=["확인된 규제 조치 이행"],
                missing_information=["추가 상품 사양"],
                raw_response={"status": "ok"},
            )
        raise TimeoutError("규제 API 응답 시간 초과")

    selected_tool_impl = _StubTool(selected_tool, selected_tool_behavior)
    tools = {
        name: (
            selected_tool_impl
            if name is selected_tool
            else _StubTool(name, _unused_tool_result)
        )
        for name in ToolName
    }
    tracking_executor = _TrackingToolExecutor(ToolExecutor(tools))
    product = Product(
        product_id="product-1",
        product_name="테스트 상품",
    )
    pipeline = CompliancePipeline(
        extractor=_FakeExtractor(product),
        selector=_FakeSelector(selected_tool),
        tool_executor=tracking_executor,
        aggregator=ResultAggregator(),
        verifier=_RuleOnlyVerifier(),
        max_retry_rounds=1,
    )

    result = pipeline.run(
        ExtractionInput(
            product_id=product.product_id,
            text_blocks=["테스트 상품 설명"],
        )
    )

    assert result.verification_status is FinalVerificationStatus.INCOMPLETE
    assert result.verification.status is VerificationStatus.TOOLS_REQUIRED
    assert result.overall_status is OverallStatus.HIGH_RISK
    assert result.findings == [valid_high_risk_finding, warning_finding]
    assert result.required_actions == ["확인된 규제 조치 이행"]
    assert result.missing_information == ["추가 상품 사양"]

    latest_tool_result = next(
        item for item in result.tool_results if item.tool_name is selected_tool
    )
    assert latest_tool_result.status is ToolStatus.PARTIAL
    assert latest_tool_result.retry_round == 1
    assert latest_tool_result.query == {"product_id": product.product_id}
    assert latest_tool_result.result == _assessment_for(selected_tool)
    assert latest_tool_result.findings == [valid_high_risk_finding, warning_finding]
    assert latest_tool_result.required_actions == ["확인된 규제 조치 이행"]
    assert latest_tool_result.missing_information == ["추가 상품 사양"]
    assert latest_tool_result.raw_response == {"status": "ok"}

    assert tracking_executor.latest_result is not None
    selected_tool_history = [
        item
        for item in tracking_executor.latest_result.tool_result_history
        if item.tool_name is selected_tool
    ]
    effective_latest = next(
        item
        for item in tracking_executor.latest_result.tool_results
        if item.tool_name is selected_tool
    )
    assert [item.status for item in selected_tool_history] == [
        ToolStatus.SUCCESS,
        ToolStatus.FAILED,
    ]
    assert [item.retry_round for item in selected_tool_history] == [0, 1]
    assert selected_tool_history[0].findings == [
        challenged_finding,
        valid_high_risk_finding,
        warning_finding,
    ]
    assert selected_tool_history[1].findings == []
    assert effective_latest.query is not selected_tool_history[0].query
    assert effective_latest.result is not selected_tool_history[0].result
    assert (
        effective_latest.required_actions
        is not selected_tool_history[0].required_actions
    )
    assert (
        effective_latest.missing_information
        is not selected_tool_history[0].missing_information
    )
    assert effective_latest.raw_response is not selected_tool_history[0].raw_response
    assert selected_tool_impl.calls == 2
    assert all(
        tool.calls == 0
        for name, tool in tools.items()
        if name is not selected_tool
    )
