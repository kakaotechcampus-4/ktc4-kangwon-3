"""케이스 더미 진단 함수. LLM·외부 API 호출 없이 단계 진행만 흉내 냄."""

import time

from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIResponseCode
from ..schemas.schemas import ExecutionEndReason, FinalAssessment, FinalVerificationStatus
from ..schemas.session import DiagnosisInput, SessionAnswer
from ..sessions.job import JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from .cases import CASES, DummyCase
from .marker import read_case

# 단계별 지연. BE가 진행 이벤트 순서 확인용
STAGE_SECONDS = 1.0
# 질문·실패는 Tool 실행 전 단계에서 멈춤
_ASK_STAGES = (PipelineStage.EXTRACTION, PipelineStage.SELECTION)
_DONE_STAGES = (
    *_ASK_STAGES,
    PipelineStage.TOOL_EXECUTION,
    PipelineStage.AGGREGATION,
    PipelineStage.VERIFICATION,
    PipelineStage.FINALIZATION,
)


def run_case_diagnosis(
    job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter,
) -> Outcome:
    """입력에 표시된 케이스대로 질문·실패·완료를 돌려준다.

    회차는 받은 답변의 마지막 회차로 셈. 케이스의 질문 회차를 다 채우면 실패 케이스는 실패, 나머지는 완료.
    질문이 3회차 이상인 케이스는 세션이 2회차 뒤 질문을 미완료 결과로 바꿈.

    Args:
        job_input: 실행 입력. source에 케이스 표시가 있어야 함.
        context: 실행 컨텍스트. 사용하지 않음.
        progress: 단계 진행 알림.

    Returns:
        Outcome: 다음 회차 질문, 파이프라인 오류 실패, 또는 케이스 결과로 완료.

    Raises:
        ValueError: 입력에 케이스 표시가 없는 경우.
    """
    case = CASES[read_case(job_input.source)]
    result = case.build(job_input.source.product_id)
    answered = max((answer.question_round for answer in job_input.answers), default=0)

    if answered < len(case.rounds):
        _run_stages(progress, _ASK_STAGES)
        return JobNeedsInput(_awaiting(result), case.rounds[answered])
    if case.fails:
        _run_stages(progress, _ASK_STAGES)
        return JobFailed(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False)
    _run_stages(progress, _DONE_STAGES)
    if job_input.answers:
        summary = f"{result.summary}\n\n{_answer_summary(case, job_input.answers)}"
        result = result.model_copy(update={"summary": summary})
    return JobDone(result)


def _awaiting(result: FinalAssessment) -> FinalAssessment:
    return result.model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def _answer_summary(case: DummyCase, answers: list[SessionAnswer]) -> str:
    texts = {question.question_key: question.question_text for questions in case.rounds for question in questions}
    lines = [f"- {texts.get(answer.question_key, answer.question_key)} → {answer.answer_text}" for answer in answers]
    return "받은 답변:\n" + "\n".join(lines)


def _run_stages(progress: ProgressReporter, stages: tuple[PipelineStage, ...]) -> None:
    for stage in stages:
        progress.stage(stage)
        time.sleep(STAGE_SECONDS)
