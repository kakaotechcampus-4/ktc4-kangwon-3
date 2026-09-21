"""Pipeline Runner의 최초 1회 실행 흐름을 검증한다."""

import pytest

from app.pipeline.runner import CompliancePipeline, _build_final_assessment
from app.schemas.agent import (
    ExtractionInput,
    ToolSelectionItem,
    ToolSelectionResponse,
)
from app.schemas.pipeline import SelectionResult
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination,
    DraftAssessment,
    FinalVerificationStatus,
    FollowUpQuestion,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)


@pytest.mark.parametrize(
    ("verification_status", "expected_final_status"),
    [
        (VerificationStatus.APPROVED, FinalVerificationStatus.VERIFIED),
        (
            VerificationStatus.APPROVED_WITH_WARNINGS,
            FinalVerificationStatus.VERIFIED_WITH_WARNINGS,
        ),
        (VerificationStatus.REVISION_REQUIRED, FinalVerificationStatus.INCOMPLETE),
        (VerificationStatus.USER_INPUT_REQUIRED, FinalVerificationStatus.INCOMPLETE),
    ],
)
def test_최초_실행은_각_단계를_순서대로_연결하고_최종_상태를_변환한다(
    verification_status: VerificationStatus,
    expected_final_status: FinalVerificationStatus,
):
    calls: list[str] = []
    source = ExtractionInput(product_id="product-1", text_blocks=["테스트 상품"])
    product = Product(product_id="product-1", product_name="테스트 상품")
    selection = ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(
                tool_name=tool_name,
                selected=False,
                reason="검토 신호 없음",
            )
            for tool_name in ToolName
        ]
    )
    tool_results = [
        ToolResult(
            tool_name=decision.tool_name,
            status=ToolStatus.SKIPPED,
            selected=False,
            selection_reason=decision.reason,
        )
        for decision in selection.decisions
    ]
    selection_result = SelectionResult(
        selection=selection,
        tool_results=tool_results,
        tool_result_history=[],
    )
    draft = DraftAssessment(
        product=product,
        selected_tools=[],
        tool_results=tool_results,
        findings=[],
        overall_status=OverallStatus.INSUFFICIENT_INFORMATION,
        summary="확인된 판단이 없습니다.",
    )
    verification = VerificationResult(status=verification_status)

    class FakeExtractor:
        def extract(self, received: ExtractionInput) -> Product:
            calls.append("extract")
            assert received == source
            return product

    class FakeSelector:
        def select(self, received: Product) -> ToolSelectionResponse:
            calls.append("select")
            assert received == product
            return selection

    class FakeToolExecutor:
        def execute_initial(
            self,
            received_product: Product,
            received_selection: ToolSelectionResponse,
        ) -> SelectionResult:
            calls.append("execute_initial")
            assert received_product == product
            assert received_selection == selection
            return selection_result

    class FakeAggregator:
        def aggregate(
            self,
            received_product: Product,
            received_result: SelectionResult,
        ) -> DraftAssessment:
            calls.append("aggregate")
            assert received_product == product
            assert received_result == selection_result
            return draft

    class FakeVerifier:
        def verify(self, received: DraftAssessment) -> VerificationResult:
            calls.append("verify")
            assert received == draft
            return verification

    pipeline = CompliancePipeline(
        extractor=FakeExtractor(),
        selector=FakeSelector(),
        tool_executor=FakeToolExecutor(),
        aggregator=FakeAggregator(),
        verifier=FakeVerifier(),
    )

    result = pipeline.run(source)

    assert calls == [
        "extract",
        "select",
        "execute_initial",
        "aggregate",
        "verify",
    ]
    assert result.assessment_id == draft.assessment_id
    assert result.verification_status is expected_final_status
    assert result.verification == verification


def test_최종_결과는_계약_필드와_검증_질문을_중복_없이_조립한다():
    product = Product(product_id="product-1", product_name="테스트 상품")
    finding = RegulatoryFinding(
        finding_id="finding-1",
        tool_name=ToolName.CUSTOMS,
        subject="수입 요건",
        determination=Determination.REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        summary="수입 전에 확인이 필요합니다.",
        rationale="상품 분류를 확정할 정보가 부족합니다.",
        assumptions=["상품이 일반 판매 목적으로 수입된다고 가정했습니다."],
    )
    tool_result = ToolResult(
        execution_id="execution-1",
        tool_name=ToolName.CUSTOMS,
        status=ToolStatus.SUCCESS,
        selected=True,
        selection_reason="수입 요건 검토 필요",
        findings=[finding],
        required_actions=["관세사에게 품목분류를 확인하세요."],
        missing_information=["상품 재질"],
    )
    draft_question = FollowUpQuestion(
        question_id="question-1",
        question="상품의 재질은 무엇인가요?",
        reason="품목분류 확인에 필요합니다.",
        related_tools=[ToolName.CUSTOMS],
        required=True,
    )
    verification_question = FollowUpQuestion(
        question_id="question-2",
        question="상품을 어떤 목적으로 수입하나요?",
        reason="수입 요건 확인에 필요합니다.",
        related_tools=[ToolName.CUSTOMS],
        required=True,
    )
    draft = DraftAssessment(
        assessment_id="assessment-1",
        product=product,
        selected_tools=[ToolName.CUSTOMS],
        tool_results=[tool_result],
        findings=[finding],
        overall_status=OverallStatus.ACTION_REQUIRED,
        summary="추가 확인과 조치가 필요합니다.",
        required_actions=["관세사에게 품목분류를 확인하세요."],
        missing_information=["상품 재질"],
        follow_up_questions=[draft_question],
    )
    # 실제 Verification Agent는 초안 질문을 검증 결과에 먼저 병합한다.
    verification = VerificationResult(
        status=VerificationStatus.USER_INPUT_REQUIRED,
        review_summary="사용자 확인이 필요합니다.",
        follow_up_questions=[draft_question, verification_question],
        checked_finding_ids=[finding.finding_id],
    )

    result = _build_final_assessment(draft, verification)

    assert result.assessment_id == draft.assessment_id
    assert result.product == draft.product
    assert result.overall_status is draft.overall_status
    assert result.summary == draft.summary
    assert result.selected_tools == draft.selected_tools
    assert result.tool_results == draft.tool_results
    assert result.findings == draft.findings
    assert result.required_actions == draft.required_actions
    assert result.missing_information == draft.missing_information
    assert result.follow_up_questions == [draft_question, verification_question]
    assert result.verification == verification
