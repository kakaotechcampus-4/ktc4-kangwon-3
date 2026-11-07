"""실제 진단 함수. 파이프라인을 실행마다 조립해 돌리고, 결과로 세션 결말을 정함.

파이프라인(pipeline/runner.py)은 진행 알림·로그·trace·다시 실행을 모름. 단계·Tool hook으로 붙임
(diagnosis/progress.py·run_log.py·tracing.py·replay.py·langsmith_trace.py). 묶는 순서는 ``_stage_hooks``.
검증 모델 검토가 실패하면 규칙 검사 결과로 진행 (통과는 재확인 필요로 바꿈, diagnosis/stages.py). 규칙 결과도 없으면 재시도 가능 실패.
파이프라인이 끝난 뒤 Tool의 부족한 정보가 남아 있으면 판매자 질문으로 넘김 (지난 회차에 물은 질문은 빼고).

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
from ..results.presenter import FIELD_LABELS
from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import ExecutionEndReason, FinalAssessment, FinalVerificationStatus, FollowUpQuestion
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from .answers import ANSWER_PREFIX
from .assembly import PipelineParts
from .langsmith_trace import stage_hook as langsmith_stage_hook, tool_hook as langsmith_tool_hook, traced_job, tracing_on
from .progress import ProgressStageHook, ProgressToolHook
from .replay import ReplaySkipHook, ReplayStopHook, StageReplay
from .run_log import error_text, log_tool_failure, mark_retry_round
from .stages import JobInputExtraction, RulesFallbackVerification
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
    tracing = tracing_on()

    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        # 기록 중엔 Tool 순차 실행 (기록기가 열린 단계·진행 중 호출을 객체 하나에 둠)
        max_parallel = 1 if current_trace() else MAX_PARALLEL_TOOLS
        executor = ToolExecutor(
            parts.tools, max_parallel=max_parallel,
            # 앞이 바깥: 진행 알림 → 실패 로그 → LangSmith
            tool_hook=chain_tool_hooks(ProgressToolHook(progress), log_tool_failure,
                                       *([langsmith_tool_hook] if tracing else [])),
        )
        pipeline = CompliancePipeline(
            extractor=JobInputExtraction(parts.extraction, job_input),
            selector=parts.selector,
            tool_executor=executor,
            aggregator=parts.aggregator,
            verifier=RulesFallbackVerification(parts.verifier),
            stage_hook=chain_stage_hooks(*_stage_hooks(job_input, progress, replay, tracing)),
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
        result = _ask_missing_information(result, job_input.previous)
        progress.stage(PipelineStage.FINALIZATION)
        if result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED:
            question_round = _next_round(job_input)
            asked = questions(result, question_round)
            trace_finish(result.termination_reason.value, result=result, question_round=question_round,
                         questions=asked)
            return JobNeedsInput(result, asked)
        trace_finish(result.termination_reason.value, result=result)
        return JobDone(result)

    return traced_job(run) if tracing else run


def _stage_hooks(job_input: DiagnosisInput, progress: ProgressReporter, replay: StageReplay | None,
                 tracing: bool = False) -> list[StageHook]:
    """단계 hook 목록. 앞이 바깥.

    로그 필드 → 진행 알림 → 다시 실행 멈춤 → trace → 다시 실행 건너뛰기 → LangSmith → 실제 단계.
    진행 알림은 trace 단계를 열기 전에, 멈춤 결말은 trace 단계가 닫힌 뒤에, replayed 표시는 trace 단계 안에 남음.
    LangSmith에는 실제로 돌린 단계만 남음 (건너뛴 단계 제외).

    Args:
        job_input: 이번 실행 입력.
        progress: 이번 실행의 진행 알림.
        replay: 단계 다시 실행 설정. 없으면 다시 실행 hook을 안 붙임.
        tracing: LangSmith 기록을 켠 실행이면 True.

    Returns:
        list[StageHook]: 바깥부터 차례로.
    """
    hooks: list[StageHook] = [mark_retry_round, ProgressStageHook(progress)]
    if replay is None:
        hooks += [TraceStageHook(job_input)]
    else:
        hooks += [ReplayStopHook(replay), TraceStageHook(job_input), ReplaySkipHook(replay)]
    return [*hooks, langsmith_stage_hook] if tracing else hooks


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


def _ask_missing_information(result: FinalAssessment, previous: FinalAssessment | None) -> FinalAssessment:
    """Tool이 남긴 부족한 정보를 판매자 질문으로 넘긴다.

    파이프라인은 Tool의 부족한 정보(missing_information, Tool이 만든 질문 문장)를 질문 칸으로 옮기지 않음.
    검증 모델이 질문을 안 만들면 답할 기회 없이 끝나서 여기서 옮김 (#495).
    지난 회차에 물은 질문은 다시 묻지 않음 (답했는데도 남았으면 답으로도 못 정한 것).
    질문 회차 상한은 세션 실행기가 봄.

    Args:
        result: 파이프라인 결과.
        previous: 지난 실행 결과. 첫 실행이면 None.

    Returns:
        FinalAssessment: 새 질문이 있으면 질문을 더하고 답변 대기로 바꾼 결과, 없으면 그대로.
    """
    asked = {question.question.strip() for question in (previous.follow_up_questions if previous else [])}
    # 직전 결과에는 그 전 회차 질문이 없어서, 상품 정보에 남은 답변 줄에서도 모음
    if previous is not None:
        asked |= {line.removeprefix(ANSWER_PREFIX).split(" → ")[0].strip()
                  for line in previous.product.listing_text if line.startswith(ANSWER_PREFIX)}
    existing = {question.question.strip() for question in result.follow_up_questions}
    added: dict[str, FollowUpQuestion] = {}
    for tool_result in result.tool_results:
        for text in (text.strip() for text in tool_result.missing_information):
            if not text or text in asked or text in existing:
                continue
            # 여러 Tool이 같은 정보를 물으면 질문 하나에 관련 Tool을 모음
            if text in added:
                if tool_result.tool_name not in added[text].related_tools:
                    added[text].related_tools.append(tool_result.tool_name)
                continue
            added[text] = FollowUpQuestion(question=text, reason="", related_tools=[tool_result.tool_name])
    if not added:
        return result
    for question in added.values():
        labels = ", ".join(FIELD_LABELS[tool] for tool in question.related_tools)
        question.reason = f"{labels} 판단에 필요한 정보예요."
    logger.info("Tool의 부족한 정보로 질문 %d개 추가 (종료 사유 %s → user_input_required)",
                len(added), result.termination_reason.value)
    return result.model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
        "follow_up_questions": [*result.follow_up_questions, *added.values()],
    })


def _next_round(job_input: DiagnosisInput) -> int:
    """이번 실행이 질문하면 쓸 회차. 답한 마지막 회차 다음."""
    return max((answer.question_round for answer in job_input.answers), default=0) + 1
