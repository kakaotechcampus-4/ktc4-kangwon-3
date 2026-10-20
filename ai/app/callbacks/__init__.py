"""AI → BE 진단 콜백: 세션 상태 변경 → 이벤트(events) → 발신함(outbox)."""

from threading import Lock

from ..sessions.events import SessionEvent, ToolProgressed
from ..sessions.executor import SessionExecutor
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

    def deliver(event: SessionEvent) -> None:
        with lock:
            # 이벤트 생성기가 세션 이벤트를 직접 받기 전까지 Tool 진행만 따로 넘김
            if isinstance(event, ToolProgressed):
                outbox.put(builder.build_tool(event.session, event.tool_name, event.status))
            else:
                outbox.put(builder.build(event.session))

    executor.subscribe(deliver)
