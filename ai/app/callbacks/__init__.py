"""AI → BE 진단 콜백: 세션 이벤트 → 콜백 이벤트(events) → 발신함(outbox)."""

from threading import Lock

from ..sessions.events import SessionEvent
from ..sessions.manager import SessionManager
from .events import AssessmentPresenter, EventBuilder
from .outbox import CallbackOutbox, CallbackSender

__all__ = ["AssessmentPresenter", "CallbackOutbox", "CallbackSender", "EventBuilder", "connect_callbacks"]


def connect_callbacks(manager: SessionManager, builder: EventBuilder, outbox: CallbackOutbox) -> None:
    """세션 이벤트마다 콜백 이벤트를 만들어 발신함에 넣도록 세션 관리자에 연결한다.

    변환 실패 등 연결 함수의 예외는 세션 관리자가 경고로 남기고 진단은 계속함.
    번호 발급과 발신함 넣기는 잠금 하나로 묶음. 여러 스레드가 같은 실행의 이벤트를 만들어도 번호 순서대로 들어감.

    Args:
        manager: 진단 세션 관리자.
        builder: 세션 이벤트 → 콜백 이벤트 변환.
        outbox: 이벤트 발신함.
    """
    lock = Lock()

    def deliver(event: SessionEvent) -> None:
        with lock:
            outbox.put(builder.build(event))

    manager.subscribe(deliver)
