"""실제 진단 함수. 파이프라인을 실행마다 조립해 돌리고, 결과로 세션 결말을 정함.

파이프라인(pipeline/runner.py)은 진행 알림을 모름. 단계 객체를 감싸 부를 때마다 단계 알림을 보냄.
재실행 회차에는 Tool 실행·집계·검증 알림이 다시 나감.
"""

from collections.abc import Callable

from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIServiceError
from ..pipeline.runner import CompliancePipeline
from ..pipeline.tool_executor import ToolExecutor
from ..schemas.agent import ExtractionInput, ToolSelectionResponse
from ..schemas.callback import PublicQuestionDto
from ..schemas.pipeline import RetryRequest, SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import DraftAssessment, ExecutionEndReason, FinalAssessment, VerificationResult
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from .assembly import PipelineParts

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
        pipeline = CompliancePipeline(
            extractor=_Extraction(parts, job_input, progress),
            selector=_Selection(parts, progress),
            tool_executor=_ToolExecution(ToolExecutor(parts.tools), progress),
            aggregator=_Aggregation(parts, progress),
            verifier=_Verification(parts, progress),
        )
        try:
            result = pipeline.run(job_input.source)
        except AIServiceError as exc:
            # 단계가 정한 실패 코드·재시도 여부를 그대로 (#450)
            return JobFailed(exc.response_code.code, exc.retryable)
        progress.stage(PipelineStage.FINALIZATION)
        if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED:
            return JobNeedsInput(result, questions(result, _next_round(job_input)))
        return JobDone(result)

    return run


def _next_round(job_input: DiagnosisInput) -> int:
    """이번 실행이 질문하면 쓸 회차. 답한 마지막 회차 다음."""
    return max((answer.question_round for answer in job_input.answers), default=0) + 1


class _Extraction:
    """추출 자리. 파이프라인이 넘기는 원래 입력 대신 실행 입력 전체로 추출 단계를 부름 (재진단이면 이전 추출 결과)."""

    def __init__(self, parts: PipelineParts, job_input: DiagnosisInput, progress: ProgressReporter) -> None:
        self._step = parts.extraction
        self._job_input = job_input
        self._progress = progress

    def run(self, source: ExtractionInput) -> Product:
        self._progress.stage(PipelineStage.EXTRACTION)
        return self._step.run(self._job_input)


class _Selection:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter) -> None:
        self._selector = parts.selector
        self._progress = progress

    def run(self, product: Product) -> ToolSelectionResponse:
        self._progress.stage(PipelineStage.SELECTION)
        return self._selector.run(product)


class _ToolExecution:
    def __init__(self, executor: ToolExecutor, progress: ProgressReporter) -> None:
        self._executor = executor
        self._progress = progress

    def execute_initial(self, product: Product, selection: ToolSelectionResponse) -> SelectionResult:
        self._progress.stage(PipelineStage.TOOL_EXECUTION)
        return self._executor.execute_initial(product, selection)

    def execute_retry(self, product: Product, previous: SelectionResult, request: RetryRequest) -> SelectionResult:
        self._progress.stage(PipelineStage.TOOL_EXECUTION)
        return self._executor.execute_retry(product, previous, request)


class _Aggregation:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter) -> None:
        self._aggregator = parts.aggregator
        self._progress = progress

    def aggregate(self, product: Product, selection_result: SelectionResult) -> DraftAssessment:
        self._progress.stage(PipelineStage.AGGREGATION)
        return self._aggregator.aggregate(product, selection_result)


class _Verification:
    def __init__(self, parts: PipelineParts, progress: ProgressReporter) -> None:
        self._verifier = parts.verifier
        self._progress = progress

    def run(self, draft: DraftAssessment) -> VerificationResult:
        self._progress.stage(PipelineStage.VERIFICATION)
        return self._verifier.run(draft)
