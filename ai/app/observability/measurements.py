"""클라이언트·Tool·추출이 남기는 측정 기록과 그 기록을 받아 가는 곳(sink)의 등록표.

기록을 남기는 코드는 지표를 몰라도 됨. 서버는 lifespan에서 지표 sink를 등록하고 종료 때 해제.
받는 쪽 오류는 경고 로그만 남기고 기록을 남긴 쪽 동작에 영향 없음.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientCall:
    """외부 API 호출 1건.

    Attributes:
        api: 호출한 서버 (law·data_go_kr·customs·safety_korea·radio·marketplace·backend·llm).
        result: 호출 결과 (ok·http_error·api_error·timeout·connect_error).
        seconds: 걸린 시간(초).
    """

    api: str
    result: str
    seconds: float


@dataclass(frozen=True)
class ToolRun:
    """Tool 실행 1건.

    Attributes:
        tool_name: Tool 이름.
        status: 실행 상태 (success·partial·failed·skipped).
        seconds: 걸린 시간(초). 건너뛰면 0.
        error_type: 실패 원인 (client·model·other). 실패가 아니면 None.
    """

    tool_name: str
    status: str
    seconds: float
    error_type: str | None = None


@dataclass(frozen=True)
class SellerRegionCut:
    """상세페이지 글 하나의 판매자 구역 자르기 결과.

    Attributes:
        site: 알아본 쇼핑몰. 모르면 unknown.
        trimmed: 구역을 실제로 잘랐는지.
    """

    site: str
    trimmed: bool


Measurement = ClientCall | ToolRun | SellerRegionCut
MeasurementSink = Callable[[Measurement], None]


class MeasurementSinkRegistry:
    """측정 기록을 받아 갈 sink 목록. 여러 스레드에서 동시에 불려도 됨."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sinks: list[MeasurementSink] = []

    def add(self, sink: MeasurementSink) -> None:
        """sink를 등록한다. 이미 있으면 그대로 둠 (같은 기록을 두 번 받지 않게).

        Args:
            sink: 측정 기록을 받는 함수.
        """
        with self._lock:
            if sink not in self._sinks:
                self._sinks.append(sink)

    def remove(self, sink: MeasurementSink) -> None:
        """sink를 해제한다. 없으면 무시.

        Args:
            sink: 등록할 때 넘긴 함수.
        """
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    @contextmanager
    def added(self, sink: MeasurementSink) -> Iterator[None]:
        """블록 안에서만 sink를 등록한다. 예외로 빠져나가도 해제.

        Args:
            sink: 측정 기록을 받는 함수.
        """
        self.add(sink)
        try:
            yield
        finally:
            self.remove(sink)

    def publish(self, record: Measurement) -> None:
        """기록 1건을 등록된 sink 전부에 넘긴다. sink 오류는 경고 로그만 남김.

        Args:
            record: 측정 기록.
        """
        # 넘기는 동안 등록·해제가 일어나도 되게 목록을 복사
        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink(record)
            except Exception:
                logger.warning("측정 기록 sink 처리 실패 (%s)", type(record).__name__, exc_info=True)


# 앱 전체가 함께 쓰는 등록표
measurement_sinks = MeasurementSinkRegistry()
