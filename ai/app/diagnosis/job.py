"""실제 진단 함수. 파이프라인을 실행마다 조립해 돌리고, 결과로 세션 결말을 정함.

파이프라인(pipeline/runner.py)은 진행 알림을 모름. 단계 객체를 감싸 부를 때마다 단계 알림을 보냄.
재실행 회차에는 Tool 실행·집계·검증 알림이 다시 나감.
Tool 진행도 Tool을 감싸서 보냄. 재실행 회차에는 다시 실행하는 Tool만 started·completed가 다시 나감.

로컬 trace를 켠 실행이면 단계마다 trace 단계를 열고 나온 값(output)을 원래 모양 그대로 남김.
다음 단계의 입력은 앞 단계의 output이라 따로 안 남김 (추출 입력만 남김). 재실행 회차는 단계마다 round로.
"""

import logging
from collections.abc import Callable

from ..agents.verification import VerificationError
from ..clients.base import mask_sensitive_params
from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIError, AIResponseCode, AIServiceError
from ..observability.logs import set_run_field
from ..observability.trace import trace_note, trace_step
from ..pipeline.runner import CompliancePipeline
from ..pipeline.tool_executor import ToolExecutor
from ..schemas.agent import ExtractionInput, ToolSelectionItem, ToolSelectionResponse
from ..schemas.callback import PublicQuestionDto
from ..schemas.pipeline import RetryRequest, SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import (
    DraftAssessment, ExecutionEndReason, FinalAssessment, ToolName, ToolResult, ToolStatus, VerificationResult,
)
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from ..tools.base import RegulatoryTool
from .answers import with_answers
from .assembly import PipelineParts

logger = logging.getLogger(__name__)

# 질문 결과 + 질문 회차 → BE에 보낼 질문
QuestionBuilder = Callable[[FinalAssessment, int], list[PublicQuestionDto]]


def build_job(parts: PipelineParts, questions: QuestionBuilder) -> DiagnosisJob:
    """파이프라인 부품으로 세션 진단 함수를 만든다.

    Args:
        parts: 기동 때 만든 파이프라인 부품.
        questions: 답변이 필요한 결과의 질문을 만드는 함수.

    Returns:
        DiagnosisJob: 실행 입력·컨텍스트·진행 알림을 받아 결말을 돌려주는 진단 함수.
    """

    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        retry_round = _RetryRound()
        pipeline = CompliancePipeline(
            extractor=_Extraction(parts, job_input, progress),
            selector=_Selection(parts, progress),
            tool_executor=_ToolExecution(ToolExecutor(_reporting_tools(parts.tools, progress)), progress, retry_round),
            aggregator=_Aggregation(parts, progress, retry_round),
            verifier=_Verification(parts, progress, retry_round),
        )
        try:
            result = pipeline.run(job_input.source)
        except AIServiceError as exc:
            # 단계가 정한 실패 코드·재시도 여부를 그대로 (#450). 세션 실행기는 이 실패를 로그로 안 남김 → 원인과 함께 기록
            # 예상한 실패 → 위치 없이 원인 예외만 한 줄로
            logger.warning("진단 단계 실패 (stage=%s, code=%s, retryable=%s): %s", exc.stage,
                           exc.response_code.code, exc.retryable, _error_text(exc.__cause__ or exc))
            return JobFailed(exc.response_code.code, exc.retryable)
        progress.stage(PipelineStage.FINALIZATION)
        if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED:
            return JobNeedsInput(result, questions(result, _next_round(job_input)))
        return JobDone(result)

    return run


def _next_round(job_input: DiagnosisInput) -> int:
    """이번 실행이 질문하면 쓸 회차. 답한 마지막 회차 다음."""
    return max((answer.question_round for answer in job_input.answers), default=0) + 1


class _RetryRound:
    """지금 Tool 재실행 회차 (0은 첫 실행). 재실행 Tool 실행이 바꾸고, 뒤따르는 집계·검증이 trace에 같이 남김."""

    def __init__(self) -> None:
        self.value = 0


class _Extraction:
    """추출 자리. 파이프라인이 넘기는 원래 입력 대신 실행 입력 전체로 추출 단계를 부름.

    재진단이면 이전 추출 결과에 이번 회차 답변을 붙여 선택 단계부터 다시 돎.
    """

    def __init__(self, parts: PipelineParts, job_input: DiagnosisInput, progress: ProgressReporter) -> None:
        self._step = parts.extraction
        self._job_input = job_input
        self._progress = progress

    def run(self, source: ExtractionInput) -> Product:
        self._progress.stage(PipelineStage.EXTRACTION)
        with trace_step("extraction"):
            trace_note("input", self._job_input)
            product = with_answers(self._step.run(self._job_input), self._job_input)
            trace_note("output", product)
            return product


class _Selection:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter) -> None:
        self._selector = parts.selector
        self._progress = progress

    def run(self, product: Product) -> ToolSelectionResponse:
        self._progress.stage(PipelineStage.SELECTION)
        with trace_step("selection"):
            selection = self._selector.run(product)
            trace_note("output", selection)
            return selection


def _reporting_tools(tools: dict[ToolName, RegulatoryTool],
                     progress: ProgressReporter) -> dict[ToolName, "_ReportingTool"]:
    """Tool마다 진행 알림을 보내는 감싸개를 씌운다. 이번 실행의 진행 알림으로 묶음."""
    return {name: _ReportingTool(tool, progress) for name, tool in tools.items()}


class _ReportingTool:
    """실행 전후로 Tool 진행 알림. 실행기가 선택된 Tool만 부르므로 started·completed만 보냄.

    Tool 예외도 completed (실패 여부는 분야 카드에서 표시). 예외는 실행기가 FAILED 결과로 바꿈.
    실행기는 원인을 남기지 않아 여기서 남기고 그대로 올림 (#497).
    """

    def __init__(self, tool: RegulatoryTool, progress: ProgressReporter) -> None:
        self._tool = tool
        self._progress = progress
        self.tool_name = tool.tool_name

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        self._progress.tool(self.tool_name, "started")
        try:
            return self._tool.execute(product, decision)
        except AIError as exc:
            # 예상한 실패(외부 API·모델·Tool 오류)는 원인만
            logger.warning("Tool 실행 실패 %s: %s", self.tool_name, _error_text(exc))
            raise
        except Exception as exc:
            # 코드 오류 가능성 → 위치까지
            logger.error("Tool 실행 실패 %s: %s", self.tool_name, _error_text(exc), exc_info=True)
            raise
        finally:
            self._progress.tool(self.tool_name, "completed")


def _error_text(exc: BaseException) -> str:
    """로그용 예외 설명. 메시지 속 URL의 키는 가림."""
    return mask_sensitive_params(f"{type(exc).__name__}: {exc}")


class _ToolExecution:
    def __init__(self, executor: ToolExecutor, progress: ProgressReporter,
                 retry_round: _RetryRound | None = None) -> None:
        self._executor = executor
        self._progress = progress
        self._round = retry_round or _RetryRound()

    def execute_initial(self, product: Product, selection: ToolSelectionResponse) -> SelectionResult:
        self._progress.stage(PipelineStage.TOOL_EXECUTION)
        with trace_step("tool_execution", round=0):
            result = self._executor.execute_initial(product, selection)
            trace_note("output", result)
        # 선택 안 된 Tool은 실행기가 부르지 않아 여기서 알림. 재실행 회차에는 보내지 않음
        for tool_result in result.tool_results:
            if tool_result.status is ToolStatus.SKIPPED:
                self._progress.tool(tool_result.tool_name, "skipped")
        return result

    def execute_retry(self, product: Product, previous: SelectionResult, request: RetryRequest) -> SelectionResult:
        # 이후 로그 줄(재실행 Tool·집계·검증)에 회차 표시
        set_run_field("retry_round", request.retry_round)
        self._round.value = request.retry_round
        self._progress.stage(PipelineStage.TOOL_EXECUTION)
        # 재실행 요청(실행할 Tool·검증 결과·직전 Tool 결과)은 앞 단계 output과 같아 회차만
        with trace_step("tool_execution", round=request.retry_round):
            result = self._executor.execute_retry(product, previous, request)
            trace_note("output", result)
            return result


class _Aggregation:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter, retry_round: _RetryRound) -> None:
        self._aggregator = parts.aggregator
        self._progress = progress
        self._round = retry_round

    def aggregate(self, product: Product, selection_result: SelectionResult) -> DraftAssessment:
        self._progress.stage(PipelineStage.AGGREGATION)
        with trace_step("aggregation", round=self._round.value):
            draft = self._aggregator.aggregate(product, selection_result)
            trace_note("output", draft)
            return draft


class _Verification:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter, retry_round: _RetryRound) -> None:
        self._verifier = parts.verifier
        self._progress = progress
        self._round = retry_round

    def run(self, draft: DraftAssessment) -> VerificationResult:
        self._progress.stage(PipelineStage.VERIFICATION)
        try:
            with trace_step("verification", round=self._round.value):
                verification = self._verifier.run(draft)
                trace_note("output", verification)
                return verification
        except VerificationError as exc:
            # 검토 ID 중복 등 모델 실수·호출 실패. 다시 돌리면 통과 가능 → 재시도 가능
            raise AIServiceError(
                response_code=AIResponseCode.PIPELINE_ERROR.value, stage=PipelineStage.VERIFICATION, retryable=True,
            ) from exc
