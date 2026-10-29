"""세션이 실행하는 진단 함수와의 계약. 진단 함수는 결과를 해석해 결말(Outcome)을 정해서 돌려줌.

세션은 결과 내용을 열어 보지 않고 결말 종류로만 다음 상태를 정함.
    - JobDone: 완료
    - JobNeedsInput: 사용자 답변이 필요해 멈춤
    - JobFailed: 진단 함수가 스스로 판단한 실패 (예: 입력 거절). 예상하지 못한 예외는 세션이 파이프라인 오류로 기록
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from ..domain.context import ExecutionContext, PipelineStage, RunType
from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import ExecutionEndReason, FinalAssessment, ToolName
from ..schemas.session import DiagnosisInput
from .errors import UnsupportedRunTypeError

# Tool 진행 상태. Tool 실행 오류도 completed (실패 여부는 분야 카드에서 표시)
ToolProgressStatus = Literal["started", "completed", "skipped"]


class ProgressReporter(Protocol):
    """진단 함수가 부르는 진행 알림. 단계 변경과 Tool 진행은 서로 다른 경로."""

    def stage(self, stage: PipelineStage) -> None: ...

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None: ...


@dataclass(frozen=True)
class JobDone:
    """진단 완료.

    Attributes:
        result: 이번 실행의 결과. 종료 사유는 user_input_required가 아님.

    Raises:
        ValueError: 결과의 종료 사유가 user_input_required인 경우.
    """

    result: FinalAssessment

    def __post_init__(self) -> None:
        if self.result.termination_reason is ExecutionEndReason.USER_INPUT_REQUIRED:
            raise ValueError("답변이 필요한 결과는 JobNeedsInput으로 돌려줘야 합니다.")


@dataclass(frozen=True)
class JobNeedsInput:
    """사용자 답변이 필요해 멈춤.

    Attributes:
        result: 질문이 담긴 이번 실행의 결과. 종료 사유는 user_input_required.
        questions: BE에 보낼 질문. 세션에 기록돼 질문 콜백·재진단 답변 검사에 쓰임.

    Raises:
        ValueError: 결과의 종료 사유가 user_input_required가 아닌 경우.
    """

    result: FinalAssessment
    questions: list[PublicQuestionDto]

    def __post_init__(self) -> None:
        if self.result.termination_reason is not ExecutionEndReason.USER_INPUT_REQUIRED:
            raise ValueError("JobNeedsInput의 결과는 종료 사유가 user_input_required여야 합니다.")


@dataclass(frozen=True)
class JobFailed:
    """진단 함수가 스스로 판단한 실패.

    Attributes:
        error_code: 실패 코드.
        retryable: 같은 요청을 다시 보내 복구 가능한지.
    """

    error_code: str
    retryable: bool


Outcome = JobDone | JobNeedsInput | JobFailed

# 실행 입력(원래 입력 + 재진단이면 이전 결과·답변), 실행 컨텍스트, 진행 알림을 받아 결말을 돌려주는 진단 함수
DiagnosisJob = Callable[[DiagnosisInput, ExecutionContext, ProgressReporter], Outcome]


def by_run_type(jobs: dict[RunType, DiagnosisJob]) -> DiagnosisJob:
    """실행 컨텍스트의 실행 종류로 진단 함수를 골라 부르는 진단 함수를 만든다.

    Args:
        jobs: 실행 종류 → 진단 함수.

    Returns:
        DiagnosisJob: 실행 종류에 맞는 진단 함수를 부르는 진단 함수.
    """
    jobs = dict(jobs)

    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        job = jobs.get(context.run_type)
        if job is None:
            raise UnsupportedRunTypeError(f"진단 함수가 연결되지 않은 실행 종류입니다: {context.run_type}")
        return job(job_input, context, progress)

    return run
