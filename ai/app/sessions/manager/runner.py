"""진단 함수 한 번 실행. 진행 알림과 결말을 세션 상태 변경으로 바꿈."""

import logging
from typing import assert_never

from ...domain.errors import AIResponseCode
from ...domain.context import ExecutionContext, PipelineStage
from ...observability.logs import run_log_context, set_run_field
from ...observability.run_summary import RunSummary, current_summary, run_summary
from ...schemas.schemas import ExecutionEndReason, FinalAssessment, FinalVerificationStatus, ToolName
from ...schemas.session import DiagnosisInput
from ..job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, Outcome, ToolProgressStatus
from ..transitions import AskUser, ChangeStage, Complete, Fail, ReportTool, Start
from .updater import SessionUpdater

logger = logging.getLogger(__name__)

# 사용자에게 질문하는 최대 회차 (#310). 넘으면 질문 대신 미완료 결과로 끝냄
MAX_QUESTION_ROUNDS = 2
# 질문 회차를 다 쓰고 미완료로 끝낼 때 결과에 붙이는 안내 (공개 진단서 notices로 나감)
QUESTION_LIMIT_NOTICE = "추가 확인이 필요한 정보가 남아 있어 진단을 끝까지 마치지 못했습니다. 판매 전 직접 확인이 필요합니다."


class _Progress:
    """세션 하나의 진행 알림. 자기 실행(run_id)의 세션에만 적용."""

    def __init__(self, updater: SessionUpdater, context: ExecutionContext) -> None:
        self._updater = updater
        self._context = context

    def stage(self, stage: PipelineStage) -> None:
        # 이후 로그 줄에 지금 단계 표시, 실행 요약에 단계 시간 기록
        set_run_field("stage", stage.value)
        if (summary := current_summary()) is not None:
            summary.enter_stage(stage)
        self._updater.apply(self._context, ChangeStage(stage))

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        self._updater.apply(self._context, ReportTool(tool_name, status))


def run_session(job: DiagnosisJob, context: ExecutionContext, updater: SessionUpdater) -> None:
    """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음.

    세션 변경은 모두 이 실행의 context로 함. 시간 초과 뒤 재접수된 새 세션은 건드리지 않음.
    실행 중 남긴 로그 줄에는 이 실행의 정보가 붙고, 단계·Tool·모델 호출은 실행 요약에 모임 (#497).

    Args:
        job: 진단 함수.
        context: 이 실행의 컨텍스트.
        updater: 상태 변경 통로.
    """
    with run_log_context(context), run_summary() as summary:
        outcome = _run_session(job, context, updater)
        if outcome is not None:
            _log_summary(outcome, summary)


def _run_session(job: DiagnosisJob, context: ExecutionContext, updater: SessionUpdater) -> Outcome | None:
    """``run_session``의 본문. 인자는 같음.

    Returns:
        Outcome | None: 세션에 기록한 결말. 실행하지 않았으면 None.
    """
    started = updater.apply(context, Start())
    # 대기 중 시간 초과로 이미 실패한 세션이면 실행하지 않음
    if started is None:
        return None
    session = started.session
    if session.started_at is not None:
        logger.info("진단 시작 (대기 %.1f초, 답변 %d개)",
                    (session.started_at - session.accepted_at).total_seconds(), len(session.answers))
    # 첫 실행은 이전 결과·답변이 비어 있음
    job_input = DiagnosisInput(source=session.source, previous=session.result, answers=session.answers)
    try:
        outcome = job(job_input, context, _Progress(updater, context))
        if isinstance(outcome, JobNeedsInput) and session.question_round >= MAX_QUESTION_ROUNDS:
            outcome = JobDone(_close_at_question_limit(outcome.result))
        # 결말 기록 실패도 진단 실패로. 실행 중으로 남으면 시간 초과까지 콜백 없이 멈춤
        match outcome:
            case JobDone(result=result):
                updater.apply(context, Complete(result))
            case JobNeedsInput(result=result, questions=questions):
                updater.apply(context, AskUser(result, questions))
            case JobFailed(error_code=error_code, retryable=retryable):
                updater.apply(context, Fail(error_code, retryable))
            case _:
                assert_never(outcome)
    except Exception:
        logger.exception("진단 실행 실패")
        # 일시적 오류인지 알 수 없어 재시도 불가로 기록. 코드 오류를 BE가 계속 재요청하지 않게 함
        outcome = JobFailed(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False)
        updater.apply(context, Fail(outcome.error_code, outcome.retryable))
    return outcome


def _log_summary(outcome: Outcome, summary: RunSummary) -> None:
    """실행이 끝날 때 상품마다 요약 한 줄 (#497). 느린 단계·비싼 상품·자주 실패하는 Tool을 고르는 용도.

    Args:
        outcome: 세션에 기록한 결말.
        summary: 이 실행의 요약 재료.
    """
    total = summary.finish()
    match outcome:
        case JobDone(result=result):
            ending = f"완료 {result.overall_status.value}, 검증 {result.verification_status.value}, " \
                     f"종료 {result.termination_reason.value}"
        case JobNeedsInput(questions=questions):
            ending = f"답변 대기, 질문 {len(questions)}개"
        case JobFailed(error_code=error_code, retryable=retryable):
            ending = f"실패 {error_code}, 재시도 {'가능' if retryable else '불가'}"
        case _:
            assert_never(outcome)
    stages = " ".join(f"{stage} {seconds:.1f}" for stage, seconds in summary.stage_seconds.items())
    tools = _format_tools(summary)
    logger.info(
        "진단 요약: %s | 총 %.1f초 | 단계(초) %s | Tool(초) %s | Tool 실행 %d회 | 모델 호출 %d회(실패 %d) "
        "토큰 입력 %d 출력 %d | 비용 %.1f원",
        ending, total, stages or "-", tools or "-", summary.tool_execution_rounds, summary.model_calls,
        summary.model_failures, summary.input_tokens, summary.output_tokens, summary.cost_krw,
    )


def _format_tools(summary: RunSummary) -> str:
    """요약의 Tool 목록. 재실행이 있으면 회차별로 ``[1] … [2] …``로 묶고, 없으면 회차 표시 없이.

    Args:
        summary: 이 실행의 요약 재료.

    Returns:
        str: ``이름 상태 초`` 목록. Tool이 없으면 빈 문자열.
    """
    rounds: dict[int, list[str]] = {}
    for tool in summary.tools:
        rounds.setdefault(tool.round, []).append(f"{tool.tool_name} {tool.status} {tool.seconds:.1f}")
    if len(rounds) <= 1:
        return ", ".join(item for items in rounds.values() for item in items)
    return " ".join(f"[{number}] {', '.join(items)}" for number, items in rounds.items())


def _close_at_question_limit(result: FinalAssessment) -> FinalAssessment:
    """질문 회차를 다 쓴 실행의 질문 결과를 미완료 결과로 바꾼다. 남은 질문은 기록용으로 그대로 둠."""
    logger.info("질문 회차 초과로 미완료 처리 (남은 질문 %d개)", len(result.follow_up_questions))
    return result.model_copy(update={
        "termination_reason": ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
        "missing_information": [*result.missing_information, QUESTION_LIMIT_NOTICE],
    })
