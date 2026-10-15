"""AI → BE 진단 콜백: 세션 상태 변경 → 이벤트(events) → 발신함(outbox)."""

from ..sessions.executor import SessionExecutor
from .events import AssessmentPresenter, EventBuilder
from .outbox import CallbackOutbox, CallbackSender, CallbackTransportError, SendResult

__all__ = [
    "AssessmentPresenter", "CallbackOutbox", "CallbackSender", "CallbackTransportError", "EventBuilder",
    "SendResult", "connect_callbacks",
]


def connect_callbacks(executor: SessionExecutor, builder: EventBuilder, outbox: CallbackOutbox) -> None:
    """세션 상태가 바뀔 때마다 이벤트를 만들어 발신함에 넣도록 실행기에 연결한다.

    변환 실패 등 연결 함수의 예외는 실행기가 경고로 남기고 진단은 계속함.

    Args:
        executor: 진단 세션 실행기.
        builder: 세션 변경 → 이벤트 변환.
        outbox: 이벤트 발신함.
    """
    executor.subscribe(lambda session: outbox.put(builder.build(session)))
