"""세션 상태 전이 규칙. 어느 상태에서 어떤 일이 가능한지는 TRANSITIONS, 상태별 성격은 STATUS_TRAITS 표에서만 정함.

apply(session, change)가 표대로 새 세션과 이벤트를 만들고, 표에 없는 조합은 거절함.
세션은 바꾸지 않고 새로 만듦. 저장·알림은 호출하는 쪽 몫.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never

from ..observability.context import PipelineStage
from ..schemas.schemas import FinalAssessment, ToolName
from ..schemas.session import DiagnosisSession, SessionStatus
from .events import AwaitingInput, Completed, Failed, SessionEvent, StageChanged, Started, ToolProgressed
from .job import ToolProgressStatus


@dataclass(frozen=True)
class Start:
    """실행 시작."""


@dataclass(frozen=True)
class ChangeStage:
    """실행 단계 변경.

    Attributes:
        stage: 새 단계.
    """

    stage: PipelineStage


@dataclass(frozen=True)
class ReportTool:
    """Tool 진행 알림. 상태는 그대로 두고 이벤트만 냄.

    Attributes:
        tool_name: 진행한 Tool.
        status: Tool 진행 상태.
    """

    tool_name: ToolName
    status: ToolProgressStatus


@dataclass(frozen=True)
class Complete:
    """결과와 함께 실행 완료.

    Attributes:
        result: 최종 결과.
    """

    result: FinalAssessment


@dataclass(frozen=True)
class AskUser:
    """사용자 답변이 필요해 실행 종료.

    Attributes:
        result: 질문이 담긴 최종 결과.
    """

    result: FinalAssessment


@dataclass(frozen=True)
class Fail:
    """실행 실패. 종료 사유가 아니라 오류 코드로 기록 (#171 §7.1.1).

    Attributes:
        error_code: 실패 코드.
        retryable: 같은 요청을 다시 보내 복구 가능한지.
    """

    error_code: str
    retryable: bool


Change = Start | ChangeStage | ReportTool | Complete | AskUser | Fail

# (지금 상태, 일어난 일) → 다음 상태. 여기 없는 조합은 거절
TRANSITIONS: dict[tuple[SessionStatus, type[Change]], SessionStatus] = {
    (SessionStatus.ACCEPTED, Start): SessionStatus.RUNNING,
    (SessionStatus.RUNNING, ChangeStage): SessionStatus.RUNNING,
    (SessionStatus.RUNNING, ReportTool): SessionStatus.RUNNING,
    (SessionStatus.RUNNING, Complete): SessionStatus.COMPLETED,
    (SessionStatus.RUNNING, AskUser): SessionStatus.AWAITING_INPUT,
    (SessionStatus.ACCEPTED, Fail): SessionStatus.FAILED,
    (SessionStatus.RUNNING, Fail): SessionStatus.FAILED,
}


@dataclass(frozen=True)
class StatusTraits:
    """상태의 성격. 상태별로 다르게 다루는 곳은 이 표만 봄.

    Attributes:
        blocks_new_accept: 같은 상품의 새 접수를 막는지 (진행 중).
        times_out: 접수 후 최대 시간이 지나면 시간 초과로 실패시키는지.
        purgeable: 보관 시간이 지나면 지우는지.
    """

    blocks_new_accept: bool
    times_out: bool
    purgeable: bool


# 상태를 추가하면 TRANSITIONS 줄과 여기 한 줄을 같이 추가
STATUS_TRAITS: dict[SessionStatus, StatusTraits] = {
    SessionStatus.ACCEPTED: StatusTraits(blocks_new_accept=True, times_out=True, purgeable=False),
    SessionStatus.RUNNING: StatusTraits(blocks_new_accept=True, times_out=True, purgeable=False),
    # 실행은 끝났지만 답변을 기다리는 중이라 새 접수는 막음
    SessionStatus.AWAITING_INPUT: StatusTraits(blocks_new_accept=True, times_out=False, purgeable=False),
    SessionStatus.COMPLETED: StatusTraits(blocks_new_accept=False, times_out=False, purgeable=True),
    SessionStatus.FAILED: StatusTraits(blocks_new_accept=False, times_out=False, purgeable=True),
}


class InvalidTransitionError(ValueError):
    """규칙표에 없는 전이를 요청한 경우. 시간 초과 뒤 늦게 온 결과 등.

    Attributes:
        status: 세션의 지금 상태.
        change: 요청한 일.
    """

    def __init__(self, status: SessionStatus, change: Change) -> None:
        super().__init__(f"{status} 상태에서는 {type(change).__name__}을 할 수 없습니다.")
        self.status = status
        self.change = change


@dataclass(frozen=True)
class Transition:
    """전이 결과.

    Attributes:
        session: 전이 후 세션. 상태가 그대로인 전이(ReportTool)면 원래 세션.
        events: 전이가 남긴 이벤트. 일어난 순서대로.
    """

    session: DiagnosisSession
    events: tuple[SessionEvent, ...]


def apply(session: DiagnosisSession, change: Change, *, now: datetime) -> Transition:
    """규칙표대로 세션에 일을 적용한다.

    Args:
        session: 지금 세션. 바꾸지 않음.
        change: 일어난 일.
        now: 변경 시각. updated_at·started_at·stage_started_at에 씀.

    Returns:
        Transition: 새 세션과 이벤트.

    Raises:
        InvalidTransitionError: 지금 상태에서 할 수 없는 일인 경우.
    """
    status = TRANSITIONS.get((session.status, type(change)))
    if status is None:
        raise InvalidTransitionError(session.status, change)

    match change:
        case Start():
            updated = _replace(session, now, status=status, started_at=now)
            return Transition(updated, (Started(updated),))
        case ChangeStage(stage=stage):
            updated = _replace(session, now, stage=stage, stage_started_at=now)
            return Transition(updated, (StageChanged(updated, stage),))
        case ReportTool(tool_name=tool_name, status=tool_status):
            # 상태·시각 그대로. Tool 진행은 기록하지 않고 알리기만
            return Transition(session, (ToolProgressed(session, tool_name, tool_status),))
        case Complete(result=result):
            updated = _replace(
                session, now, status=status, termination_reason=result.termination_reason, result=result,
            )
            return Transition(updated, (Completed(updated, result),))
        case AskUser(result=result):
            updated = _replace(
                session, now, status=status, termination_reason=result.termination_reason, result=result,
            )
            return Transition(updated, (AwaitingInput(updated, result),))
        case Fail(error_code=error_code, retryable=retryable):
            updated = _replace(session, now, status=status, error_code=error_code, retryable=retryable)
            return Transition(updated, (Failed(updated, error_code, retryable),))
        case _:
            # 표에 줄만 추가하고 처리를 빠뜨린 경우
            assert_never(change)


def _replace(session: DiagnosisSession, now: datetime, **changes: Any) -> DiagnosisSession:
    """바꾼 값으로 새 세션을 만든다. 검증(UTC 정규화 등)을 다시 거치도록 model_copy 대신 새로 만듦."""
    return DiagnosisSession.model_validate({**dict(session), **changes, "updated_at": now})
