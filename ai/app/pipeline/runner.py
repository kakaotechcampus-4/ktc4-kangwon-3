"""최초 실행과 재실행을 연결하고 종료 정책에 따라 마지막 결과를 반환한다."""

from enum import StrEnum
from typing import Protocol

from .early_stop import has_no_progress
from ..schemas.agent import ExtractionInput, ToolSelectionResponse
from ..schemas.pipeline import RetryRequest, SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import (
    DraftAssessment,
    ExecutionEndReason,
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

    def execute_retry(
        self,
        product: Product,
        selection_result: SelectionResult,
        retry_request: RetryRequest,
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
    """Verification 상태를 Pipeline의 다음 행동으로 변환한다."""

    action_by_status = {
        VerificationStatus.APPROVED: _PipelineNextAction.COMPLETE,
        VerificationStatus.APPROVED_WITH_WARNINGS: _PipelineNextAction.COMPLETE,
        VerificationStatus.USER_INPUT_REQUIRED: _PipelineNextAction.AWAIT_USER_INPUT,
        VerificationStatus.REVISION_REQUIRED: _PipelineNextAction.STOP_FOR_REVISION,
        VerificationStatus.TOOLS_REQUIRED: _PipelineNextAction.RETRY_TOOLS,
    }
    action = action_by_status.get(verification.status)
    if action is None:
        raise ValueError(f"처리할 수 없는 검증 결과 상태입니다: {verification.status}")
    return action


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
        verification=verification.model_copy(deep=True),
        latest_tool_results=[
            result.model_copy(deep=True)
            for result in selection_result.tool_results
        ],
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
        VerificationStatus.TOOLS_REQUIRED: FinalVerificationStatus.INCOMPLETE,
    }
    
    result = status_map.get(status)

    if result is None:
        raise ValueError(f"매핑되지 않은 검증 결과 상태입니다: {status}")
    return result


def _build_final_assessment(
    draft: DraftAssessment,
    verification: VerificationResult,
    *,
    termination_reason: ExecutionEndReason,
) -> FinalAssessment:
    """검증을 마친 초안을 외부에 반환할 최종 결과로 조립한다."""
    return FinalAssessment(
        assessment_id=draft.assessment_id,
        product=draft.product,
        verification_status=_to_final_status(verification.status),
        termination_reason=termination_reason,
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
        max_retry_rounds: int = 3,
    ) -> None:
        if isinstance(max_retry_rounds, bool) or not isinstance(
            max_retry_rounds, int
        ):
            raise TypeError("max_retry_rounds는 정수여야 합니다.")
        if max_retry_rounds < 0:
            raise ValueError("max_retry_rounds는 0 이상이어야 합니다.")
        self._extractor = extractor
        self._selector = selector
        self._tool_executor = tool_executor
        self._aggregator = aggregator
        self._verifier = verifier
        self._max_retry_rounds = max_retry_rounds

    def run(self, source: ExtractionInput) -> FinalAssessment:
        product: Product = self._extractor.extract(source)
        selection: ToolSelectionResponse = self._selector.select(product)
        selection_result: SelectionResult = self._tool_executor.execute_initial(
            product,
            selection,
        )
        draft: DraftAssessment = self._aggregator.aggregate(product, selection_result)
        verification: VerificationResult = self._verifier.verify(draft)

        retry_round = 0
        while True:
            action = _determine_next_action(verification)
            # 검증이 다른 종료 분기로 전환되면 반복 비교보다 그 판단을 우선한다.
            if action is not _PipelineNextAction.RETRY_TOOLS:
                termination_reason = {
                    _PipelineNextAction.COMPLETE: ExecutionEndReason.COMPLETED,
                    _PipelineNextAction.AWAIT_USER_INPUT: ExecutionEndReason.USER_INPUT_REQUIRED,
                    _PipelineNextAction.STOP_FOR_REVISION: ExecutionEndReason.REVISION_REQUIRED,
                }[action]
                break
            if retry_round >= self._max_retry_rounds:
                termination_reason = ExecutionEndReason.RETRY_LIMIT_EXCEEDED
                break

            # 주입된 구성 요소가 입력을 변경해도 비교 기준이 오염되지 않도록 보존한다.
            previous_result = selection_result.model_copy(deep=True)
            previous_verification = verification.model_copy(deep=True)
            retry_round += 1
            retry_request = _build_retry_request(
                verification,
                selection_result,
                retry_round=retry_round,
            )
            selection_result = self._tool_executor.execute_retry(
                product,
                selection_result,
                retry_request,
            )
            draft = self._aggregator.aggregate(product, selection_result)
            verification = self._verifier.verify(draft)

            if has_no_progress(
                previous_result,
                previous_verification,
                selection_result,
                verification,
                executed_tools=retry_request.requested_tools,
                retry_round=retry_round,
            ):
                # 마지막 허용 회차에서도 동일 결과가 확인되면 그 사유를 우선 기록한다.
                termination_reason = ExecutionEndReason.NO_PROGRESS
                break

        return _build_final_assessment(
            draft, verification, termination_reason=termination_reason,
        )
