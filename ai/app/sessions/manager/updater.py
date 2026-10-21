"""세션 상태 변경의 단일 통로. 전이표대로 바꿔 저장하고, 전이가 남긴 이벤트를 구독자에게 알림."""

import logging
from collections.abc import Callable
from datetime import datetime

from ...observability.context import ExecutionContext
from ...schemas.session import DiagnosisSession
from ..events import SessionEvent
from ..store import SessionStore
from ..transitions import Change, InvalidTransitionError, Transition, apply

logger = logging.getLogger(__name__)

# 세션 이벤트마다 호출. 콜백 전송기 자리
SessionListener = Callable[[SessionEvent], None]


class SessionUpdater:
    """실행(run_id) 하나의 세션에 일을 적용하고 이벤트를 알린다."""

    def __init__(self, store: SessionStore, clock: Callable[[], datetime]) -> None:
        """상태 변경 통로를 만든다.

        Args:
            store: 세션 저장소.
            clock: 현재 시각 함수. 변경 시각에 씀.
        """
        self._store = store
        self._clock = clock
        self._listeners: list[SessionListener] = []

    def subscribe(self, listener: SessionListener) -> None:
        """세션 이벤트마다 부를 함수를 등록한다.

        Args:
            listener: 세션 이벤트를 받는 함수.
        """
        self._listeners.append(listener)

    def apply(self, context: ExecutionContext, change: Change) -> Transition | None:
        """이 실행의 세션에 전이표대로 일을 적용하고 이벤트를 구독자에게 알린다.

        Args:
            context: 이 실행의 컨텍스트.
            change: 일어난 일.

        Returns:
            Transition | None: 전이 결과. 재접수로 다른 실행이 됐거나, 지금 상태에서 할 수 없는 일
                (시간 초과 뒤 늦게 온 결과 등)이면 None.

        Raises:
            ValueError: 전이가 내용을 거절한 경우 (AskUser 질문 검사). 세션은 그대로.
        """
        try:
            return self.replace(context, lambda session: apply(session, change, now=self._clock()))
        except InvalidTransitionError as e:
            logger.warning("세션 상태와 맞지 않는 변경 무시 (product_id=%s, run_id=%s): %s",
                           context.product_id, context.run_id, e)
            return None

    def replace(
        self, context: ExecutionContext, change: Callable[[DiagnosisSession], Transition],
    ) -> Transition | None:
        """이 실행의 세션을 change가 만든 전이로 바꾸고 이벤트를 알린다. 요청 검사가 필요한 변경(재진단)용.

        Args:
            context: 이 실행의 컨텍스트.
            change: 지금 세션을 받아 전이 결과를 돌려주는 함수. 거절은 예외로.

        Returns:
            Transition | None: 전이 결과. 세션이 없거나 재접수로 다른 실행이 됐으면 None.

        Raises:
            Exception: change가 낸 예외. 세션은 그대로.
        """
        transition = self._store.replace(context, change)
        if transition is None:
            return None
        for event in transition.events:
            self._publish(event)
        return transition

    def _publish(self, event: SessionEvent) -> None:
        """세션 이벤트를 구독자에게 전달한다. 구독자 오류는 실행에 영향 없음."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.warning("세션 구독자 처리 실패 (product_id=%s, event=%s)",
                               event.session.context.product_id, type(event).__name__, exc_info=True)
