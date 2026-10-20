"""AI → BE 진단 콜백: 세션 상태 변경 → 이벤트(events) → 발신함(outbox)."""

from threading import Lock

from ..schemas.schemas import ToolName
from ..schemas.session import DiagnosisSession
from ..sessions.executor import SessionExecutor
from ..sessions.job import ToolProgressStatus
from .events import AssessmentPresenter, EventBuilder
from .http import HttpCallbackSender
from .outbox import CallbackOutbox, CallbackSender, CallbackTransportError, SendResult

__all__ = [
    "AssessmentPresenter", "CallbackOutbox", "CallbackSender", "CallbackTransportError", "EventBuilder",
    "HttpCallbackSender", "SendResult", "connect_callbacks",
]


def connect_callbacks(executor: SessionExecutor, builder: EventBuilder, outbox: CallbackOutbox) -> None:
    """세션 상태 변경·Tool 진행마다 이벤트를 만들어 발신함에 넣도록 실행기에 연결한다.

    변환 실패 등 연결 함수의 예외는 실행기가 경고로 남기고 진단은 계속함.
    번호 발급과 발신함 넣기는 잠금 하나로 묶음. 여러 스레드가 같은 실행의 이벤트를 만들어도 번호 순서대로 들어감.

    Args:
        executor: 진단 세션 실행기.
        builder: 세션 변경·Tool 진행 → 이벤트 변환.
        outbox: 이벤트 발신함.
    """
    lock = Lock()

    def deliver(session: DiagnosisSession) -> None:
        with lock:
            outbox.put(builder.build(session))

    def deliver_tool(session: DiagnosisSession, tool_name: ToolName, status: ToolProgressStatus) -> None:
        with lock:
            outbox.put(builder.build_tool(session, tool_name, status))

    executor.subscribe(deliver)
    executor.subscribe_tool(deliver_tool)
