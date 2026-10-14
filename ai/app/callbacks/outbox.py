"""BE로 콜백 이벤트를 보내는 프로세스 안 발신함 (#301).

메시지 큐 대신 상품별 대기열 + 전송 스레드 몇 개.
    - 같은 상품의 이벤트는 넣은 순서대로, 한 번에 한 스레드만 보냄
    - 한 상품이 재시도로 기다려도 다른 상품은 막히지 않음
    - 2xx 성공, 5xx·타임아웃·연결 실패는 지수 백오프 + 지터로 재시도, 나머지(400·401·409 등)는 재시도 없이 기록
세션이 메모리에 있어 재시작 시 남은 이벤트도 같이 사라짐. 못 보낸 이벤트는 로그로만 남김.
"""

import logging
import random
import threading
from collections import deque
from collections.abc import Callable
from queue import Queue
from typing import Protocol

from ..schemas.callback import PublicProductEvent

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 30.0


class CallbackTransportError(RuntimeError):
    """응답을 받지 못한 전송 실패(타임아웃·연결 실패). 재시도 대상."""


class CallbackSender(Protocol):
    """이벤트 하나를 BE로 보내는 쪽. 실제 HTTP 전송은 [콜백 2/5]."""

    def send(self, event: PublicProductEvent) -> int:
        """이벤트를 보내고 HTTP 상태 코드를 돌려준다.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        ...


class CallbackOutbox:
    """상품별 순서를 지키며 콜백 이벤트를 보낸다.

    Args:
        sender: 이벤트 전송.
        workers: 전송 스레드 수. 동시에 보내는 상품 수 상한.
        max_retries: 재시도 횟수 상한 (첫 전송 제외).
        base_delay: 첫 재시도 대기 시간(초). 재시도마다 2배.
        max_delay: 재시도 대기 시간 상한(초).
        wait: 대기 함수. 기다리는 중 종료되면 True. 테스트에서 실제로 기다리지 않을 때 주입.
        jitter: 0~1 난수 함수. 대기 시간을 절반~전체 사이로 흩뜨림.
    """

    def __init__(
        self,
        sender: CallbackSender,
        *,
        workers: int = 4,
        max_retries: int = MAX_RETRIES,
        base_delay: float = BASE_DELAY_SECONDS,
        max_delay: float = MAX_DELAY_SECONDS,
        wait: Callable[[float], bool] | None = None,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if workers < 1:
            raise ValueError("workers는 1 이상이어야 합니다.")
        self._sender = sender
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter
        self._stopping = threading.Event()
        self._wait = wait or self._stopping.wait
        self._lock = threading.Condition()
        # 상품별 보낼 이벤트. 키가 있으면 어떤 스레드가 맡고 있거나 맡을 차례
        self._lanes: dict[str, deque[PublicProductEvent]] = {}
        self._ready: Queue[str | None] = Queue()
        self._closed = False
        self._threads = [
            threading.Thread(target=self._work, name=f"callback-{index}", daemon=True) for index in range(workers)
        ]
        for thread in self._threads:
            thread.start()

    def put(self, events: list[PublicProductEvent]) -> None:
        """이벤트를 보낼 차례에 넣는다. 닫힌 뒤에는 넣지 않고 기록만 함.

        Args:
            events: 보낼 순서대로. 상품이 섞여도 됨.
        """
        with self._lock:
            for event in events:
                if self._closed:
                    _log_dropped(event, "발신함 종료 후 들어온 이벤트")
                    continue
                lane = self._lanes.get(event.product_id)
                if lane is None:
                    self._lanes[event.product_id] = deque([event])
                    self._ready.put(event.product_id)
                else:
                    lane.append(event)

    def close(self, timeout: float) -> int:
        """새 이벤트를 받지 않고, timeout초까지 남은 이벤트를 보낸 뒤 스레드를 멈춘다.

        Args:
            timeout: 남은 이벤트를 기다릴 최대 시간(초).

        Returns:
            int: 보내지 못하고 버린 이벤트 수.
        """
        with self._lock:
            self._closed = True
            self._lock.wait_for(lambda: not self._lanes, timeout=timeout)
            # 기다리는 중인 재시도를 깨워 멈추게 함
            self._stopping.set()
            dropped = 0
            for lane in self._lanes.values():
                for event in lane:
                    _log_dropped(event, "종료 시간 안에 보내지 못함")
                    dropped += 1
                lane.clear()
        for _ in self._threads:
            self._ready.put(None)
        for thread in self._threads:
            thread.join(timeout=1)
        return dropped

    def _work(self) -> None:
        """상품 하나를 맡아 그 상품의 이벤트가 빌 때까지 차례로 보낸다."""
        while (product_id := self._ready.get()) is not None:
            while True:
                with self._lock:
                    lane = self._lanes.get(product_id)
                    if not lane:
                        self._lanes.pop(product_id, None)
                        self._lock.notify_all()
                        break
                    event = lane.popleft()
                self._deliver(event)

    def _deliver(self, event: PublicProductEvent) -> None:
        """이벤트 하나를 재시도 규칙대로 보낸다. 예외는 밖으로 내지 않음."""
        for attempt in range(self._max_retries + 1):
            if attempt and self._wait(self._delay(attempt)):
                _log_dropped(event, "종료로 재시도 중단")
                return
            try:
                status = self._sender.send(event)
            except CallbackTransportError as exc:
                reason = f"전송 실패({type(exc).__name__})"
            except Exception:
                logger.exception("콜백 전송 중 예상하지 못한 오류 (event_id=%s)", event.event_id)
                return
            else:
                if 200 <= status < 300:
                    return
                if status < 500:
                    _log_dropped(event, f"재시도 대상 아님(HTTP {status})")
                    return
                reason = f"HTTP {status}"
            if attempt < self._max_retries:
                logger.warning("콜백 재시도 예정 %d/%d: %s (event_id=%s, product_id=%s)",
                               attempt + 1, self._max_retries, reason, event.event_id, event.product_id)
        _log_dropped(event, f"재시도 {self._max_retries}회 초과")

    def _delay(self, attempt: int) -> float:
        """attempt번째 재시도 전 대기 시간. 상한 안에서 2배씩, 절반~전체 사이로 흩뜨림."""
        delay = min(self._max_delay, self._base_delay * 2 ** (attempt - 1))
        return delay * (0.5 + self._jitter() / 2)


def _log_dropped(event: PublicProductEvent, reason: str) -> None:
    # 본문(진단서·질문)은 남기지 않고 식별자만
    logger.warning("콜백 이벤트를 보내지 못함: %s (event_id=%s, event_type=%s, product_id=%s, run_id=%s, sequence=%d)",
                   reason, event.event_id, event.event_type, event.product_id, event.run_id, event.sequence)
