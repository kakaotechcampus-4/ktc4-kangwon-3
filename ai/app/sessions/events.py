"""세션 상태 전이가 남기는 이벤트. 구독자(콜백 등)는 세션을 비교하지 않고 이벤트 종류로 무슨 일인지 앎.

모든 이벤트는 전이 직후의 세션을 함께 담음. 실행 식별(diagnosis_id·product_id·run_id)은 session.context에서.
"""

from dataclasses import dataclass

from ..observability.context import PipelineStage
from ..schemas.schemas import FinalAssessment, ToolName
from ..schemas.session import DiagnosisSession
from .job import ToolProgressStatus


@dataclass(frozen=True)
class SessionEvent:
    """세션 이벤트 공통.

    Attributes:
        session: 전이 직후의 세션.
    """

    session: DiagnosisSession


@dataclass(frozen=True)
class Started(SessionEvent):
    """실행 시작 (ACCEPTED → RUNNING)."""


@dataclass(frozen=True)
class StageChanged(SessionEvent):
    """실행 중 단계 변경.

    Attributes:
        stage: 새 단계.
    """

    stage: PipelineStage


@dataclass(frozen=True)
class ToolProgressed(SessionEvent):
    """실행 중 Tool 진행. 세션 상태는 바뀌지 않음.

    Attributes:
        tool_name: 진행한 Tool.
        status: Tool 진행 상태.
    """

    tool_name: ToolName
    status: ToolProgressStatus


@dataclass(frozen=True)
class Completed(SessionEvent):
    """실행 완료 (RUNNING → COMPLETED).

    Attributes:
        result: 최종 결과.
    """

    result: FinalAssessment


@dataclass(frozen=True)
class AwaitingInput(SessionEvent):
    """사용자 답변 대기로 실행 종료 (RUNNING → AWAITING_INPUT).

    Attributes:
        result: 질문이 담긴 최종 결과.
    """

    result: FinalAssessment


@dataclass(frozen=True)
class Failed(SessionEvent):
    """실행 실패 (ACCEPTED·RUNNING → FAILED).

    Attributes:
        error_code: 실패 코드.
        retryable: 같은 요청을 다시 보내 복구 가능한지.
    """

    error_code: str
    retryable: bool
