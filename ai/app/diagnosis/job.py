"""실제 진단 함수. 파이프라인을 실행마다 조립해 돌리고, 결과로 세션 결말을 정함.

파이프라인(pipeline/runner.py)은 진행 알림·로그·trace·다시 실행을 모름. 단계·Tool hook으로 붙임
(diagnosis/progress.py·run_log.py·tracing.py·replay.py). 묶는 순서는 ``_stage_hooks``.

로컬 trace를 켠 실행이면 결말(finish)엔 종료 이유와 최종 결과, 질문하면 질문 회차·질문, 단계 실패면 실패 코드와 처음 실패한 위치.
답변 뒤 재진단은 새 실행이라 새 파일. 이전 결과·답변은 추출 input에 들어 있음.
단계 다시 실행(replay)이면 시작 단계 앞 단계는 저장한 output을 쓰고 trace 단계에 replayed 표시.
"""

import logging
from collections.abc import Callable

from ..agents.verification import VerificationError
from ..config.session import MAX_PARALLEL_TOOLS
from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIResponseCode, AIServiceError
from ..observability.trace import current_trace, trace_finish
from ..pipeline.hooks import StageHook, chain_stage_hooks, chain_tool_hooks
from ..pipeline.runner import CompliancePipeline
from ..pipeline.tool_executor import ToolExecutor
from ..schemas.agent import ExtractionInput
from ..schemas.callback import PublicQuestionDto
from ..schemas.product import Product
from ..schemas.schemas import ExecutionEndReason, FinalAssessment
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from .answers import with_answers
from .assembly import PipelineParts
from .progress import ProgressStageHook, ProgressToolHook
from .replay import ReplaySkipHook, ReplayStopHook, StageReplay
from .run_log import error_text, log_tool_failure, mark_retry_round
from .tracing import TraceStageHook

logger = logging.getLogger(__name__)

# 질문 결과 + 질문 회차 → BE에 보낼 질문
QuestionBuilder = Callable[[FinalAssessment, int], list[PublicQuestionDto]]


def build_job(parts: PipelineParts, questions: QuestionBuilder, replay: StageReplay | None = None) -> DiagnosisJob:
    """파이프라인 부품으로 세션 진단 함수를 만든다.

    Args:
        parts: 기동 때 만든 파이프라인 부품.
        questions: 답변이 필요한 결과의 질문을 만드는 함수.
        replay: 단계 다시 실행 설정 (로컬 CLI). 서버는 None.

    Returns:
        DiagnosisJob: 실행 입력·컨텍스트·진행 알림을 받아 결말을 돌려주는 진단 함수.
    """

    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        # 기록 중엔 Tool 순차 실행 (기록기가 열린 단계·진행 중 호출을 객체 하나에 둠)
        max_parallel = 1 if current_trace() else MAX_PARALLEL_TOOLS
        executor = ToolExecutor(
            parts.tools, max_parallel=max_parallel,
            # 앞이 바깥: 진행 알림 → 실패 로그
            tool_hook=chain_tool_hooks(ProgressToolHook(progress), log_tool_failure),
        )
        pipeline = CompliancePipeline(
            extractor=_Extraction(parts, job_input),
            selector=parts.selector,
            tool_executor=executor,
            aggregator=parts.aggregator,
            verifier=parts.verifier,
            stage_hook=chain_stage_hooks(*_stage_hooks(job_input, progress, replay)),
        )
        try:
            result = pipeline.run(job_input.source)
        except (AIServiceError, VerificationError) as exc:
            failure = _stage_failure(exc)
            # 세션 실행기는 이 실패를 로그로 안 남김 → 원인과 함께 기록
            # 예상한 실패 → 위치 없이 원인 예외만 한 줄로
            logger.warning("진단 단계 실패 (stage=%s, code=%s, retryable=%s): %s", failure.stage,
                           failure.response_code.code, failure.retryable, error_text(failure.__cause__ or failure))
            trace_finish("failed", failure, stage=failure.stage, code=failure.response_code.code,
                         retryable=failure.retryable)
            return JobFailed(failure.response_code.code, failure.retryable)
        progress.stage(PipelineStage.FINALIZATION)
        if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED:
            question_round = _next_round(job_input)
            asked = questions(result, question_round)
            trace_finish(result.termination_reason.value, result=result, question_round=question_round,
                         questions=asked)
            return JobNeedsInput(result, asked)
        trace_finish(result.termination_reason.value, result=result)
        return JobDone(result)

    return run


def _stage_hooks(job_input: DiagnosisInput, progress: ProgressReporter, replay: StageReplay | None) -> list[StageHook]:
    """단계 hook 목록. 앞이 바깥.

    로그 필드 → 진행 알림 → 다시 실행 멈춤 → trace → 다시 실행 건너뛰기 → 실제 단계.
    진행 알림은 trace 단계를 열기 전에, 멈춤 결말은 trace 단계가 닫힌 뒤에, replayed 표시는 trace 단계 안에 남음.

    Args:
        job_input: 이번 실행 입력.
        progress: 이번 실행의 진행 알림.
        replay: 단계 다시 실행 설정. 없으면 다시 실행 hook을 안 붙임.

    Returns:
        list[StageHook]: 바깥부터 차례로.
    """
    hooks: list[StageHook] = [mark_retry_round, ProgressStageHook(progress)]
    if replay is None:
        return [*hooks, TraceStageHook(job_input)]
    return [*hooks, ReplayStopHook(replay), TraceStageHook(job_input), ReplaySkipHook(replay)]


def _stage_failure(exc: AIServiceError | VerificationError) -> AIServiceError:
    """단계 실패를 세션 실패로 바꾼다.

    Args:
        exc: 파이프라인에서 올라온 단계 실패.

    Returns:
        AIServiceError: 단계가 정한 실패는 그대로 (#450), 검증 실패는 재시도 가능한 파이프라인 오류 (원인은 검증 실패).
    """
    if isinstance(exc, AIServiceError):
        return exc
    # 검토 ID 중복 등 모델 실수·호출 실패. 다시 돌리면 통과 가능 → 재시도 가능
    failure = AIServiceError(
        response_code=AIResponseCode.PIPELINE_ERROR.value, stage=PipelineStage.VERIFICATION, retryable=True,
    )
    failure.__cause__ = exc
    return failure


def _next_round(job_input: DiagnosisInput) -> int:
    """이번 실행이 질문하면 쓸 회차. 답한 마지막 회차 다음."""
    return max((answer.question_round for answer in job_input.answers), default=0) + 1


class _Extraction:
    """추출 자리. 파이프라인이 넘기는 원래 입력 대신 실행 입력 전체로 추출 단계를 부름.

    재진단이면 이전 추출 결과에 이번 회차 답변을 붙여 선택 단계부터 다시 돎.
    다시 실행에서 저장한 추출 결과를 쓰면 이 자리는 안 불림 (저장한 결과엔 답변이 이미 붙어 있음).
    """

    def __init__(self, parts: PipelineParts, job_input: DiagnosisInput) -> None:
        self._step = parts.extraction
        self._job_input = job_input

    def run(self, source: ExtractionInput) -> Product:
        return with_answers(self._step.run(self._job_input), self._job_input)
