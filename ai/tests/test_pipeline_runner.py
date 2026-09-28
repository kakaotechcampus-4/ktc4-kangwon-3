"""Pipeline Runner의 최초 1회 실행 흐름을 검증한다."""

import pytest

from app.pipeline.runner import (
    CompliancePipeline,
    _build_final_assessment,
    _build_retry_request,
    _determine_next_action,
    _PipelineNextAction,
)
from app.schemas.agent import (
    ExtractionInput,
    ToolSelectionItem,
    ToolSelectionResponse,
)
from app.schemas.pipeline import RetryRequest, SelectionResult
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
    ("verification", "expected_action"),
    [
        (
            VerificationResult(status=VerificationStatus.APPROVED),
            _PipelineNextAction.COMPLETE,
        ),
        (
            VerificationResult(status=VerificationStatus.APPROVED_WITH_WARNINGS),
            _PipelineNextAction.COMPLETE,
        ),
        (
            VerificationResult(status=VerificationStatus.USER_INPUT_REQUIRED),
            _PipelineNextAction.AWAIT_USER_INPUT,
        ),
        (
            VerificationResult(status=VerificationStatus.REVISION_REQUIRED),
            _PipelineNextAction.STOP_FOR_REVISION,
        ),
        (
            VerificationResult(
                status=VerificationStatus.TOOLS_REQUIRED,
                additional_tools_required=[ToolName.RADIO],
            ),
            _PipelineNextAction.RETRY_TOOLS,
        ),
    ],
)
def test_검증_결과를_pipeline의_다음_행동으로_변환한다(
    verification: VerificationResult,
    expected_action: _PipelineNextAction,
):
    assert _determine_next_action(verification) is expected_action


def test_추가_tool_분기는_다음_회차의_재실행_요청을_생성한다():
    selection = ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(
                tool_name=tool_name,
                selected=False,
                reason="최초 실행에서는 검토 신호 없음",
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
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )

    result = _build_retry_request(
        verification,
        selection_result,
        retry_round=1,
    )

    assert isinstance(result, RetryRequest)
    assert result.retry_round == 1
    assert result.requested_tools == [ToolName.RADIO]
    assert result.verification == verification
    assert result.latest_tool_results == tool_results


def test_재실행_요청은_현재_Tool_결과를_독립된_스냅샷으로_보존한다():
    selection = ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(
                tool_name=tool_name,
                selected=False,
                reason="최초 실행에서는 검토 신호 없음",
            )
            for tool_name in ToolName
        ]
    )
    selection_result = SelectionResult(
        selection=selection,
        tool_results=[
            ToolResult(
                tool_name=decision.tool_name,
                status=ToolStatus.SKIPPED,
                selected=False,
                selection_reason=decision.reason,
            )
            for decision in selection.decisions
        ],
        tool_result_history=[],
    )
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )

    request = _build_retry_request(
        verification,
        selection_result,
        retry_round=1,
    )
    snapshot = request.model_copy(deep=True)

    selection_result.tool_results[0].selection_reason = "요청 생성 이후 변경됨"
    verification.additional_tools_required.append(ToolName.ELECTRICAL)

    assert request == snapshot
    assert request.verification is not verification
    assert all(
        request_result is not current_result
        for request_result, current_result in zip(
            request.latest_tool_results,
            selection_result.tool_results,
            strict=True,
        )
    )


def test_재실행_회차는_최신_Tool_결과의_회차보다_커야_한다():
    latest_result = ToolResult(
        execution_id="radio-retry-1",
        retry_round=1,
        tool_name=ToolName.RADIO,
        status=ToolStatus.SUCCESS,
        selected=True,
        selection_reason="1회차 전파 규제 재검토",
    )
    verification = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )

    with pytest.raises(ValueError, match="최신 Tool 결과의 회차보다 커야"):
        RetryRequest(
            retry_round=1,
            requested_tools=[ToolName.RADIO],
            verification=verification,
            latest_tool_results=[latest_result],
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
def test_재실행이_필요하지_않으면_각_단계를_한_번씩_실행한다(
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


def test_추가_Tool이_필요하면_재실행한_결과를_재종합하고_재검증한다():
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
    initial_tool_results = [
        ToolResult(
            tool_name=decision.tool_name,
            status=ToolStatus.SKIPPED,
            selected=False,
            selection_reason=decision.reason,
        )
        for decision in selection.decisions
    ]
    initial_result = SelectionResult(
        selection=selection,
        tool_results=initial_tool_results,
        tool_result_history=[],
    )

    retry_selection = selection.model_copy(deep=True)
    radio_decision = next(
        decision
        for decision in retry_selection.decisions
        if decision.tool_name is ToolName.RADIO
    )
    radio_decision.selected = True
    radio_decision.reason = "검증 결과 추가 검토 필요"
    radio_result = ToolResult(
        execution_id="radio-retry-1",
        retry_round=1,
        tool_name=ToolName.RADIO,
        status=ToolStatus.SUCCESS,
        selected=True,
        selection_reason=radio_decision.reason,
    )
    retried_tool_results = [
        radio_result
        if result.tool_name is ToolName.RADIO
        else result.model_copy(deep=True)
        for result in initial_tool_results
    ]
    retried_result = SelectionResult(
        selection=retry_selection,
        tool_results=retried_tool_results,
        tool_result_history=[radio_result],
    )
    initial_draft = DraftAssessment(
        product=product,
        selected_tools=[],
        tool_results=initial_tool_results,
        findings=[],
        overall_status=OverallStatus.INSUFFICIENT_INFORMATION,
        summary="추가 Tool 검토가 필요합니다.",
    )
    retried_draft = DraftAssessment(
        product=product,
        selected_tools=[ToolName.RADIO],
        tool_results=retried_tool_results,
        findings=[],
        overall_status=OverallStatus.LIKELY_COMPLIANT,
        summary="재실행 후 추가 조치가 확인되지 않았습니다.",
    )
    tools_required = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )
    approved = VerificationResult(status=VerificationStatus.APPROVED)

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
            return initial_result

        def execute_retry(
            self,
            received_product: Product,
            received_result: SelectionResult,
            retry_request: RetryRequest,
        ) -> SelectionResult:
            calls.append("execute_retry")
            assert received_product == product
            assert received_result == initial_result
            assert retry_request.retry_round == 1
            assert retry_request.requested_tools == [ToolName.RADIO]
            assert retry_request.latest_tool_results == initial_tool_results
            return retried_result

    class FakeAggregator:
        def aggregate(
            self,
            received_product: Product,
            received_result: SelectionResult,
        ) -> DraftAssessment:
            calls.append(
                "aggregate_initial"
                if not received_result.tool_result_history
                else "aggregate_retry"
            )
            assert received_product == product
            if received_result == initial_result:
                return initial_draft
            assert received_result == retried_result
            return retried_draft

    class FakeVerifier:
        def verify(self, received: DraftAssessment) -> VerificationResult:
            if received == initial_draft:
                calls.append("verify_initial")
                return tools_required
            calls.append("verify_retry")
            assert received == retried_draft
            return approved

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
        "aggregate_initial",
        "verify_initial",
        "execute_retry",
        "aggregate_retry",
        "verify_retry",
    ]
    assert result.summary == retried_draft.summary
    assert result.tool_results == retried_result.tool_results
    assert result.verification_status is FinalVerificationStatus.VERIFIED
    assert result.verification == approved


@pytest.mark.parametrize(
    ("last_verification", "expected_final_status"),
    [
        (
            VerificationResult(status=VerificationStatus.APPROVED),
            FinalVerificationStatus.VERIFIED,
        ),
        (
            VerificationResult(
                status=VerificationStatus.TOOLS_REQUIRED,
                additional_tools_required=[ToolName.RADIO],
            ),
            FinalVerificationStatus.INCOMPLETE,
        ),
        (
            VerificationResult(status=VerificationStatus.USER_INPUT_REQUIRED),
            FinalVerificationStatus.INCOMPLETE,
        ),
        (
            VerificationResult(status=VerificationStatus.REVISION_REQUIRED),
            FinalVerificationStatus.INCOMPLETE,
        ),
    ],
)
def test_Tool_재실행은_최대_3회이며_회차별_결과를_다음_입력으로_연결한다(
    last_verification: VerificationResult,
    expected_final_status: FinalVerificationStatus,
):
    source = ExtractionInput(product_id="product-1", text_blocks=["테스트 상품"])
    product = Product(product_id="product-1", product_name="테스트 상품")
    selection = ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(
                tool_name=tool_name,
                selected=tool_name is ToolName.RADIO,
                reason=(
                    "전파 규제 검토"
                    if tool_name is ToolName.RADIO
                    else "검토 신호 없음"
                ),
            )
            for tool_name in ToolName
        ]
    )
    initial_tool_results = [
        ToolResult(
            execution_id="radio-initial" if decision.selected else None,
            retry_round=0,
            tool_name=decision.tool_name,
            status=ToolStatus.SUCCESS if decision.selected else ToolStatus.SKIPPED,
            selected=decision.selected,
            selection_reason=decision.reason,
        )
        for decision in selection.decisions
    ]
    initial_result = SelectionResult(
        selection=selection,
        tool_results=initial_tool_results,
        tool_result_history=[
            result.model_copy(deep=True)
            for result in initial_tool_results
            if result.status is not ToolStatus.SKIPPED
        ],
    )
    tools_required = VerificationResult(
        status=VerificationStatus.TOOLS_REQUIRED,
        additional_tools_required=[ToolName.RADIO],
    )
    verifications = [tools_required, tools_required, tools_required, last_verification]
    retry_rounds: list[int] = []
    extraction_calls = 0
    selection_calls = 0
    aggregate_calls = 0
    verification_calls = 0

    class FakeExtractor:
        def extract(self, received: ExtractionInput) -> Product:
            nonlocal extraction_calls
            extraction_calls += 1
            assert received == source
            return product

    class FakeSelector:
        def select(self, received: Product) -> ToolSelectionResponse:
            nonlocal selection_calls
            selection_calls += 1
            assert received == product
            return selection

    class FakeToolExecutor:
        def execute_initial(
            self,
            received_product: Product,
            received_selection: ToolSelectionResponse,
        ) -> SelectionResult:
            assert received_product == product
            assert received_selection == selection
            return initial_result

        def execute_retry(
            self,
            received_product: Product,
            received_result: SelectionResult,
            retry_request: RetryRequest,
        ) -> SelectionResult:
            assert received_product == product
            assert retry_request.latest_tool_results == received_result.tool_results
            retry_rounds.append(retry_request.retry_round)

            updated_result = received_result.model_copy(deep=True)
            radio_result = next(
                result
                for result in updated_result.tool_results
                if result.tool_name is ToolName.RADIO
            )
            radio_result.execution_id = f"radio-retry-{retry_request.retry_round}"
            radio_result.retry_round = retry_request.retry_round
            updated_result.tool_result_history.append(radio_result.model_copy(deep=True))
            return updated_result

    class FakeAggregator:
        def aggregate(
            self,
            received_product: Product,
            received_result: SelectionResult,
        ) -> DraftAssessment:
            nonlocal aggregate_calls
            aggregate_calls += 1
            assert received_product == product
            return DraftAssessment(
                product=product,
                selected_tools=[ToolName.RADIO],
                tool_results=received_result.tool_results,
                findings=[],
                overall_status=OverallStatus.INSUFFICIENT_INFORMATION,
                summary="추가 Tool 검토가 필요합니다.",
            )

    class FakeVerifier:
        def verify(self, received: DraftAssessment) -> VerificationResult:
            nonlocal verification_calls
            assert received.product == product
            result = verifications[verification_calls]
            verification_calls += 1
            return result

    pipeline = CompliancePipeline(
        extractor=FakeExtractor(),
        selector=FakeSelector(),
        tool_executor=FakeToolExecutor(),
        aggregator=FakeAggregator(),
        verifier=FakeVerifier(),
    )

    result = pipeline.run(source)

    assert retry_rounds == [1, 2, 3]
    assert extraction_calls == 1
    assert selection_calls == 1
    assert aggregate_calls == 4
    assert verification_calls == 4
    assert result.verification_status is expected_final_status
    assert result.verification == last_verification


def test_최대_Tool_재실행_횟수는_음수일_수_없다():
    with pytest.raises(ValueError, match="0 이상"):
        CompliancePipeline(
            extractor=object(),
            selector=object(),
            tool_executor=object(),
            aggregator=object(),
            verifier=object(),
            max_retry_rounds=-1,
        )


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
