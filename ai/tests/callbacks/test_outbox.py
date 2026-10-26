"""콜백 발신함의 순서·재시도·종료 동작을 가짜 전송부로 확인한다. 실제로 기다리지 않음."""

import logging
import threading

import pytest

from app.callbacks.outbox import CallbackOutbox
from app.clients.backend import CallbackTransportError, SendResult
from app.schemas.callback import ProductProgressEvent, PublicPipelineStage


def _event(product_id: str = "p-1", sequence: int = 1) -> ProductProgressEvent:
    return ProductProgressEvent(
        event_id=f"{product_id}-{sequence}", diagnosis_id="d-1", product_id=product_id, run_id=f"run-{product_id}",
        sequence=sequence, stage=PublicPipelineStage.EXTRACTION, stage_status="started",
    )


class _Sender:
    """보낸 이벤트를 기록하고, event_id별로 정해 둔 응답을 차례로 돌려준다. 정하지 않으면 200.

    응답은 상태 코드, (상태 코드, BE 응답 코드), 예외 중 하나.
    """

    def __init__(self, responses: dict[str, list] | None = None) -> None:
        self.responses = {key: list(value) for key, value in (responses or {}).items()}
        self.sent: list[str] = []
        self._lock = threading.Lock()

    def send(self, event) -> SendResult:
        with self._lock:
            self.sent.append(event.event_id)
            queue = self.responses.get(event.event_id)
            response = queue.pop(0) if queue else 200
        if isinstance(response, Exception):
            raise response
        return SendResult(*response) if isinstance(response, tuple) else SendResult(response)


def _outbox(sender, delays: list[float] | None = None, **options) -> CallbackOutbox:
    record = delays if delays is not None else []
    return CallbackOutbox(sender, wait=lambda delay: record.append(delay) or False, jitter=lambda: 1.0, **options)


def test_같은_상품은_넣은_순서대로_보낸다():
    sender = _Sender()
    outbox = _outbox(sender, workers=3)

    outbox.put([_event("p-1", n) for n in range(1, 6)])

    assert outbox.close(timeout=5) == 0
    assert sender.sent == [f"p-1-{n}" for n in range(1, 6)]


@pytest.mark.parametrize("failure", [500, 503, CallbackTransportError("timeout")])
def test_5xx와_전송_실패는_백오프로_재시도한다(failure):
    sender = _Sender({"p-1-1": [failure, failure, 200]})
    delays: list[float] = []
    outbox = _outbox(sender, delays, base_delay=1.0, max_delay=30.0)

    outbox.put([_event()])
    outbox.close(timeout=5)

    assert sender.sent == ["p-1-1"] * 3
    assert delays == [1.0, 2.0]


def test_재시도는_최대_5회이고_대기_시간은_상한을_넘지_않는다(caplog):
    sender = _Sender({"p-1-1": [500] * 10})
    delays: list[float] = []
    outbox = _outbox(sender, delays, base_delay=10.0, max_delay=30.0)

    with caplog.at_level(logging.WARNING, logger="app.callbacks.outbox"):
        outbox.put([_event(), _event(sequence=2)])
        outbox.close(timeout=5)

    # 첫 전송 + 재시도 5회, 포기한 뒤에도 다음 이벤트는 보냄
    assert sender.sent == ["p-1-1"] * 6 + ["p-1-2"]
    assert delays == [10.0, 20.0, 30.0, 30.0, 30.0]
    assert "재시도 5회 초과" in caplog.text


@pytest.mark.parametrize("status", [400, 401, 404, 409])
def test_4xx는_재시도하지_않고_기록한다(status, caplog):
    sender = _Sender({"p-1-1": [status]})

    with caplog.at_level(logging.WARNING, logger="app.callbacks.outbox"):
        outbox = _outbox(sender)
        outbox.put([_event()])
        outbox.close(timeout=5)

    assert sender.sent == ["p-1-1"]
    assert f"HTTP {status}" in caplog.text


def test_BE가_다시_보내_달라고_한_409_COMMON_009는_재시도한다():
    # 202 응답 저장 전에 콜백이 먼저 도착했거나 락 대기가 넘친 경우 (#329)
    sender = _Sender({"p-1-1": [(409, "COMMON-009"), (409, "COMMON-009"), 200]})
    delays: list[float] = []
    outbox = _outbox(sender, delays)

    outbox.put([_event()])
    outbox.close(timeout=5)

    assert sender.sent == ["p-1-1"] * 3
    assert delays == [1.0, 2.0]


def test_상태_전이_불가_409_COMMON_010은_재시도하지_않는다(caplog):
    sender = _Sender({"p-1-1": [(409, "COMMON-010")]})

    with caplog.at_level(logging.WARNING, logger="app.callbacks.outbox"):
        outbox = _outbox(sender)
        outbox.put([_event()])
        outbox.close(timeout=5)

    assert sender.sent == ["p-1-1"]
    assert "HTTP 409 COMMON-010" in caplog.text


def test_지터는_대기_시간을_절반부터_전체_사이로_흩뜨린다():
    sender = _Sender({"p-1-1": [500, 200]})
    delays: list[float] = []
    outbox = CallbackOutbox(sender, wait=lambda delay: delays.append(delay) or False, jitter=lambda: 0.0,
                            base_delay=4.0)

    outbox.put([_event()])
    outbox.close(timeout=5)

    assert delays == [2.0]


def test_한_상품이_막혀도_다른_상품은_보낸다():
    release = threading.Event()
    blocked_sent = threading.Event()

    class _Blocking(_Sender):
        def send(self, event):
            if event.product_id == "slow":
                blocked_sent.set()
                release.wait(5)
            return super().send(event)

    sender = _Blocking()
    outbox = _outbox(sender, workers=2)
    outbox.put([_event("slow")])
    assert blocked_sent.wait(5)
    outbox.put([_event("fast", n) for n in range(1, 4)])

    # slow가 막혀 있는 동안 fast는 모두 나감
    for _ in range(100):
        if sender.sent.count("fast-3"):
            break
        threading.Event().wait(0.01)
    assert sender.sent == ["fast-1", "fast-2", "fast-3"]

    release.set()
    outbox.close(timeout=5)
    assert sender.sent[-1] == "slow-1"


def test_종료_시간_안에_못_보낸_이벤트는_버리고_수를_돌려준다():
    release = threading.Event()

    class _Stuck(_Sender):
        def send(self, event):
            release.wait(5)
            return super().send(event)

    outbox = CallbackOutbox(_Stuck(), workers=1)
    outbox.put([_event(sequence=n) for n in range(1, 4)])
    # 종료 대기(0.05초)가 끝난 뒤 막힌 전송을 풀어 스레드가 멈출 수 있게 함
    threading.Timer(0.2, release.set).start()

    dropped = outbox.close(timeout=0.05)

    # 1번은 전송 중이었고 2·3번은 대기열에서 버림
    assert dropped == 2


def test_재시도_대기_중_종료하면_재시도를_멈춘다():
    sender = _Sender({"p-1-1": [500] * 10})
    outbox = CallbackOutbox(sender, base_delay=60.0)
    outbox.put([_event()])

    outbox.close(timeout=0.05)

    assert sender.sent == ["p-1-1"]


def test_닫힌_뒤에_넣은_이벤트는_보내지_않는다(caplog):
    sender = _Sender()
    outbox = _outbox(sender)
    outbox.close(timeout=1)

    with caplog.at_level(logging.WARNING, logger="app.callbacks.outbox"):
        outbox.put([_event()])

    assert sender.sent == []
    assert "종료 후" in caplog.text


def test_전송_스레드는_1개_이상():
    with pytest.raises(ValueError):
        CallbackOutbox(_Sender(), workers=0)
