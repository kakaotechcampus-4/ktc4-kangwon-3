"""에이전트 실행 기록(AgentRunMeta)을 받아 가는 곳(sink)의 등록표.

에이전트는 호출 1건이 끝날 때마다 등록된 sink 전부에 기록을 넘김. 에이전트를 만드는 코드는 sink를 몰라도 됨.
    - 서버: lifespan에서 지표 sink 등록, 종료 때 해제
    - 평가 러너: added()로 실행하는 동안만 등록
받는 쪽 오류는 경고 로그만 남기고 에이전트 결과에 영향 없음.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.base.meta import AgentRunMeta

logger = logging.getLogger(__name__)

# 호출 1건의 실행 정보와 기록 대상 ID(상품 ID)를 받는 함수
AgentSink = Callable[["AgentRunMeta", str], None]


class AgentSinkRegistry:
    """에이전트 실행 기록을 받아 갈 sink 목록. 여러 실행 스레드에서 동시에 불려도 됨."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sinks: list[AgentSink] = []

    def add(self, sink: AgentSink) -> None:
        """sink를 등록한다. 이미 있으면 그대로 둠 (같은 기록을 두 번 받지 않게).

        Args:
            sink: 실행 정보와 기록 대상 ID를 받는 함수.
        """
        with self._lock:
            if sink not in self._sinks:
                self._sinks.append(sink)

    def remove(self, sink: AgentSink) -> None:
        """sink를 해제한다. 없으면 무시.

        Args:
            sink: 등록할 때 넘긴 함수.
        """
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    @contextmanager
    def added(self, sink: AgentSink) -> Iterator[None]:
        """블록 안에서만 sink를 등록한다. 예외로 빠져나가도 해제.

        Args:
            sink: 실행 정보와 기록 대상 ID를 받는 함수.
        """
        self.add(sink)
        try:
            yield
        finally:
            self.remove(sink)

    def publish(self, meta: "AgentRunMeta", subject_id: str) -> None:
        """호출 1건의 기록을 등록된 sink 전부에 넘긴다. sink 오류는 경고 로그만 남김.

        Args:
            meta: 호출 1건의 실행 정보.
            subject_id: 기록 대상 ID (상품 ID).
        """
        # 넘기는 동안 등록·해제가 일어나도 되게 목록을 복사
        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink(meta, subject_id)
            except Exception:
                logger.warning("에이전트 실행 기록 sink 처리 실패 (component=%s, subject_id=%s)",
                               meta.component, subject_id, exc_info=True)


# 앱 전체가 함께 쓰는 등록표
agent_sinks = AgentSinkRegistry()
