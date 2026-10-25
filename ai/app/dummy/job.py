"""시나리오 더미 진단 함수. LLM·외부 API 호출 없이 단계 진행만 흉내 냄."""

import time

from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIResponseCode
from ..schemas.session import DiagnosisInput
from ..sessions.job import JobDone, JobFailed, JobNeedsInput, Outcome, ProgressReporter
from .results import QUESTIONS, awaiting_result, final_result
from .scenario import DummyFlow, read_scenario

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
# 흐름별 질문 회차 수
_ROUNDS = {
    DummyFlow.NONE: 0,
    DummyFlow.ONE_ROUND: 1,
    DummyFlow.TWO_ROUNDS: 2,
    DummyFlow.FAILED: 0,
    DummyFlow.FAILED_AFTER_ANSWER: 1,
}
_FAILS = {DummyFlow.FAILED, DummyFlow.FAILED_AFTER_ANSWER}


def run_scenario_diagnosis(
    job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter,
) -> Outcome:
    """입력에 표시된 시나리오대로 질문·실패·완료를 돌려준다.

    회차는 받은 답변의 마지막 회차로 셈. 흐름의 질문 회차를 다 채우면 실패 흐름은 실패, 나머지는 완료.

    Args:
        job_input: 실행 입력. source에 시나리오 표시가 있어야 함.
        context: 실행 컨텍스트. 사용하지 않음.
        progress: 단계 진행 알림.

    Returns:
        Outcome: 다음 회차 질문, 파이프라인 오류 실패, 또는 결과 종류에 맞는 완료.

    Raises:
        ValueError: 입력에 시나리오 표시가 없는 경우.
    """
    scenario = read_scenario(job_input.source)
    product_id = job_input.source.product_id
    answered = max((answer.question_round for answer in job_input.answers), default=0)

    if answered < _ROUNDS[scenario.flow]:
        _run_stages(progress, _ASK_STAGES)
        return JobNeedsInput(awaiting_result(product_id), QUESTIONS[answered + 1])
    if scenario.flow in _FAILS:
        _run_stages(progress, _ASK_STAGES)
        return JobFailed(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False)
    _run_stages(progress, _DONE_STAGES)
    return JobDone(final_result(product_id, scenario.result, job_input.answers))


def _run_stages(progress: ProgressReporter, stages: tuple[PipelineStage, ...]) -> None:
    for stage in stages:
        progress.stage(stage)
        time.sleep(STAGE_SECONDS)
