"""에이전트와 파이프라인 구성 요소의 최초 실행 흐름을 연결한다."""

from enum import StrEnum
from typing import Protocol

from ..schemas.agent import ExtractionInput, ToolSelectionResponse
from ..schemas.pipeline import RetryRequest, SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import (
    DraftAssessment,
    FinalAssessment,
    FinalVerificationStatus,
    VerificationResult,
    VerificationStatus,
)


class ExtractionStage(Protocol):
    def extract(self, source: ExtractionInput) -> Product: ...


class SelectionStage(Protocol):
    def select(self, product: Product) -> ToolSelectionResponse: ...


class ToolExecutionStage(Protocol):
    def execute_initial(
        self,
        product: Product,
        selection: ToolSelectionResponse,
    ) -> SelectionResult: ...


class AggregationStage(Protocol):
    def aggregate(
        self,
        product: Product,
        selection_result: SelectionResult,
    ) -> DraftAssessment: ...


class VerificationStage(Protocol):
    def verify(self, draft: DraftAssessment) -> VerificationResult: ...


class _PipelineNextAction(StrEnum):
    """검증 결과를 바탕으로 Pipeline이 수행할 내부 행동."""

    COMPLETE = "complete"
    AWAIT_USER_INPUT = "await_user_input"
    STOP_FOR_REVISION = "stop_for_revision"
    RETRY_TOOLS = "retry_tools"


def _determine_next_action(
    verification: VerificationResult,
) -> _PipelineNextAction:
    """
    검증 결과를 우선순위에 따라 Pipeline의 다음 행동으로 변환한다.

    critical issue    → STOP_FOR_REVISION
    사용자 입력 필요     → AWAIT_USER_INPUT
    추가 Tool 필요      → RETRY_TOOLS
    승인·경고 포함 승인  → COMPLETE
    그 외 수정 필요     → STOP_FOR_REVISION
    """
    if any(issue.severity == "critical" for issue in verification.issues):
        return _PipelineNextAction.STOP_FOR_REVISION
    if verification.status is VerificationStatus.USER_INPUT_REQUIRED or any(
        question.required for question in verification.follow_up_questions
    ):
        return _PipelineNextAction.AWAIT_USER_INPUT
    if verification.additional_tools_required:
        return _PipelineNextAction.RETRY_TOOLS
    if verification.status in {
        VerificationStatus.APPROVED,
        VerificationStatus.APPROVED_WITH_WARNINGS,
    }:
        return _PipelineNextAction.COMPLETE
    if verification.status is VerificationStatus.REVISION_REQUIRED:
        return _PipelineNextAction.STOP_FOR_REVISION

    raise ValueError(f"처리할 수 없는 검증 결과 상태입니다: {verification.status}")


def _build_retry_request(
    verification: VerificationResult,
    selection_result: SelectionResult,
    *,
    retry_round: int,
) -> RetryRequest:
    """추가 Tool 실행 분기에서 다음 회차의 내부 요청을 만든다."""
    if _determine_next_action(verification) is not _PipelineNextAction.RETRY_TOOLS:
        raise ValueError("추가 Tool 실행이 필요한 검증 결과가 아닙니다.")
    return RetryRequest(
        retry_round=retry_round,
        requested_tools=verification.additional_tools_required,
        verification=verification,
        latest_tool_results=selection_result.tool_results,
    )


def _to_final_status(status: VerificationStatus) -> FinalVerificationStatus:
    """검증 결과 상태를 최종 응답의 검증 상태로 변환한다."""
    status_map = {
        VerificationStatus.APPROVED: FinalVerificationStatus.VERIFIED,
        VerificationStatus.APPROVED_WITH_WARNINGS: (
            FinalVerificationStatus.VERIFIED_WITH_WARNINGS
        ),
        VerificationStatus.REVISION_REQUIRED: FinalVerificationStatus.INCOMPLETE,
        VerificationStatus.USER_INPUT_REQUIRED: FinalVerificationStatus.INCOMPLETE,
    }
    
    result = status_map.get(status)

    if result is None:
      raise ValueError(f"매핑되지 않은 검증 결과 상태입니다: {status}")
    return result


def _build_final_assessment(
    draft: DraftAssessment,
    verification: VerificationResult,
) -> FinalAssessment:
    """검증을 마친 초안을 외부에 반환할 최종 결과로 조립한다."""
    return FinalAssessment(
        assessment_id=draft.assessment_id,
        product=draft.product,
        verification_status=_to_final_status(verification.status),
        overall_status=draft.overall_status,
        summary=draft.summary,
        selected_tools=draft.selected_tools,
        tool_results=draft.tool_results,
        findings=draft.findings,
        required_actions=draft.required_actions,
        missing_information=draft.missing_information,
        # Verification Agent가 초안 질문까지 병합한 목록을 반환한다.
        follow_up_questions=verification.follow_up_questions,
        verification=verification,
    )


class CompliancePipeline:
    """에이전트의 판단을 직접 구현하지 않고 실행 순서와 상태를 관리한다."""

    def __init__(
        self,
        extractor: ExtractionStage,
        selector: SelectionStage,
        tool_executor: ToolExecutionStage,
        aggregator: AggregationStage,
        verifier: VerificationStage,
    ) -> None:
        self._extractor = extractor
        self._selector = selector
        self._tool_executor = tool_executor
        self._aggregator = aggregator
        self._verifier = verifier

    def run(self, source: ExtractionInput) -> FinalAssessment:
        product: Product = self._extractor.extract(source)
        selection: ToolSelectionResponse = self._selector.select(product)
        selection_result: SelectionResult = self._tool_executor.execute_initial(
            product,
            selection,
        )
        draft: DraftAssessment = self._aggregator.aggregate(product, selection_result)
        verification: VerificationResult = self._verifier.verify(draft)

        return _build_final_assessment(draft, verification)
