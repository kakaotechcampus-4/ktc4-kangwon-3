"""진단 함수 한 번 실행. 진행 알림과 결말을 세션 상태 변경으로 바꿈."""

import logging
from typing import assert_never

from ...errors import AIResponseCode
from ...observability.context import ExecutionContext, PipelineStage
from ...schemas.schemas import ExecutionEndReason, FinalAssessment, FinalVerificationStatus, ToolName
from ...schemas.session import DiagnosisInput
from ..job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, ToolProgressStatus
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
        self._updater.apply(self._context, ChangeStage(stage))

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        self._updater.apply(self._context, ReportTool(tool_name, status))


def run_session(job: DiagnosisJob, context: ExecutionContext, updater: SessionUpdater) -> None:
    """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음.

    세션 변경은 모두 이 실행의 context로 함. 시간 초과 뒤 재접수된 새 세션은 건드리지 않음.

    Args:
        job: 진단 함수.
        context: 이 실행의 컨텍스트.
        updater: 상태 변경 통로.
    """
    started = updater.apply(context, Start())
    # 대기 중 시간 초과로 이미 실패한 세션이면 실행하지 않음
    if started is None:
        return
    session = started.session
    # 첫 실행은 이전 결과·답변이 비어 있음
    job_input = DiagnosisInput(source=session.source, previous=session.result, answers=session.answers)
    try:
        outcome = job(job_input, context, _Progress(updater, context))
    except Exception:
        logger.exception("진단 실행 실패 (product_id=%s, run_id=%s)", context.product_id, context.run_id)
        # 일시적 오류인지 알 수 없어 재시도 불가로 기록. 코드 오류를 BE가 계속 재요청하지 않게 함
        updater.apply(context, Fail(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False))
        return
    if isinstance(outcome, JobNeedsInput) and session.question_round >= MAX_QUESTION_ROUNDS:
        outcome = JobDone(_close_at_question_limit(outcome.result, context))
    match outcome:
        case JobDone(result=result):
            updater.apply(context, Complete(result))
        case JobNeedsInput(result=result, questions=questions):
            updater.apply(context, AskUser(result, questions))
        case JobFailed(error_code=error_code, retryable=retryable):
            updater.apply(context, Fail(error_code, retryable))
        case _:
            assert_never(outcome)


def _close_at_question_limit(result: FinalAssessment, context: ExecutionContext) -> FinalAssessment:
    """질문 회차를 다 쓴 실행의 질문 결과를 미완료 결과로 바꾼다. 남은 질문은 기록용으로 그대로 둠."""
    logger.warning(
        "질문 회차 초과로 미완료 처리 (product_id=%s, run_id=%s, 남은 질문 %d개)",
        context.product_id, context.run_id, len(result.follow_up_questions),
    )
    return result.model_copy(update={
        "termination_reason": ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
        "missing_information": [*result.missing_information, QUESTION_LIMIT_NOTICE],
    })
