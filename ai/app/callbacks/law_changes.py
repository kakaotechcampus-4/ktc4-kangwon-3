"""법령 점검이 찾은 변경을 BE로 보낸다 (#673).

보내는 건 근거로 쓰는 판이 바뀐 변경(APPLIED)만. 새 판 발표(ANNOUNCED)는 아직 시행 전이고,
건너뛴 판(SKIPPED)은 사람이 확인할 일이라 로그로만 남김.

점검이 목록을 먼저 덮어써 못 보낸 변경은 다음 점검에서 다시 안 잡힘. BE 쪽에서 유실을 알 방법도 없어
진단 콜백보다 오래 재시도함. 그래도 못 보내면 오류 로그와 측정 기록을 남기고, 재전송은 로그를 보고 사람이 함.
"""

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from ..clients.backend import CallbackTransportError, SendResult
from ..db import LawChange, LawChangeKind
from ..observability.measurements import CallbackOutcome, measurement_sinks
from ..schemas.callback import LawChangeCallbackRequest, PublicLawChangeDto
from ..schemas.schemas import ToolName

logger = logging.getLogger(__name__)

_DATE_FORMAT = "%Y%m%d"
EVENT_TYPE = "law_changes"
# 대기 합계 약 12.5분 (30초·1분·2분·4분·5분). BE 배포와 겹쳐도 넘어가게 함
MAX_RETRIES = 5
BASE_DELAY_SECONDS = 30.0
MAX_DELAY_SECONDS = 300.0
# 다시 보내면 되는 BE 응답 코드. COMMON-003: 같은 변경이 동시에 저장되어 겹침, COMMON-009: 락 대기 초과
RETRYABLE_CODES = frozenset({"COMMON-003", "COMMON-009"})


class LawChangeSender(Protocol):
    """변경 묶음을 BE로 보내는 쪽. 실제 HTTP 전송은 clients.backend.BackendLawChangeClient."""

    def send(self, request: LawChangeCallbackRequest) -> SendResult:
        """변경 묶음을 보내고 BE 응답을 돌려준다.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        ...


class LawChangeNotifier:
    """법령 점검의 변경을 받아 BE로 보낸다. refresh_laws의 on_change로 끼움.

    점검 스레드에서 돌아 재시도 대기 동안 그 스레드를 잡고 있음. 서버 종료 때 close로 대기를 끊음.

    Args:
        sender: 변경 묶음 전송.
        max_retries: 재시도 횟수 상한 (첫 전송 제외).
        base_delay: 첫 재시도 대기 시간(초). 재시도마다 2배.
        max_delay: 재시도 대기 시간 상한(초).
        wait: 대기 함수. 기다리는 중 종료되면 True. 테스트에서 실제로 기다리지 않을 때 주입.
    """

    def __init__(
        self,
        sender: LawChangeSender,
        *,
        max_retries: int = MAX_RETRIES,
        base_delay: float = BASE_DELAY_SECONDS,
        max_delay: float = MAX_DELAY_SECONDS,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self._sender = sender
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._stopping = threading.Event()
        self._wait = wait or self._stopping.wait

    def __call__(self, changes: list[LawChange]) -> None:
        """변경 중 보낼 것이 있으면 BE로 보낸다. 전송 실패는 밖으로 내지 않음.

        Args:
            changes: 법령 점검이 찾은 변경.
        """
        request = to_callback_request(changes)
        if request is not None:
            self._deliver(request)

    def close(self) -> None:
        """기다리는 중인 재시도를 깨워 멈추게 한다."""
        self._stopping.set()

    def _deliver(self, request: LawChangeCallbackRequest) -> None:
        """변경 묶음을 재시도 규칙대로 보낸다. BE가 중복을 무시하므로 묶음 전체를 다시 보내도 됨."""
        for attempt in range(self._max_retries + 1):
            if attempt and self._wait(self._delay(attempt)):
                _drop(request, "shutdown", "종료로 재시도 중단", retries=attempt - 1)
                return
            try:
                result = self._sender.send(request)
            except CallbackTransportError as exc:
                reason = f"전송 실패({type(exc).__name__})"
            except Exception as exc:
                _drop(request, "error", f"예상하지 못한 오류({type(exc).__name__}: {exc})", retries=attempt)
                return
            else:
                if 200 <= result.status < 300:
                    _record(retries=attempt)
                    logger.info("법령 변경 %d건을 BE로 보냄 (재시도 %d회)", len(request.changes), attempt)
                    return
                reason = f"HTTP {result.status}" + (f" {result.code}" if result.code else "")
                if not _retryable(result):
                    _drop(request, "not_retryable", f"재시도 대상 아님({reason})", retries=attempt)
                    return
            if attempt < self._max_retries:
                # 중간 재시도는 DEBUG. 포기할 때만 남김 (BE 장애 때 Sentry 로그 절약, #612)
                logger.debug("법령 변경 전송 재시도 예정 %d/%d: %s", attempt + 1, self._max_retries, reason)
        _drop(request, "retry_exhausted", f"재시도 {self._max_retries}회 초과({reason})", retries=self._max_retries)

    def _delay(self, attempt: int) -> float:
        """attempt번째 재시도 전 대기 시간. 상한 안에서 2배씩. 보내는 쪽이 하나라 흩뜨리지 않음."""
        return min(self._max_delay, self._base_delay * 2 ** (attempt - 1))


def _retryable(result: SendResult) -> bool:
    """5xx, 또는 BE가 다시 보내면 된다고 한 코드. 상태 코드와 상관없이 코드로 봄."""
    return result.status >= 500 or result.code in RETRYABLE_CODES


def _record(*, retries: int, drop_reason: str | None = None) -> None:
    """묶음 1건의 최종 결과를 측정 기록으로 남긴다."""
    measurement_sinks.publish(CallbackOutcome(
        event_type=EVENT_TYPE, delivered=drop_reason is None, retries=retries, drop_reason=drop_reason,
    ))


def _drop(request: LawChangeCallbackRequest, drop_reason: str, reason: str, *, retries: int) -> None:
    """못 보낸 묶음을 남긴다. 다음 점검에서 안 잡혀 오류 로그로 알리고, 재전송에 쓸 값을 같이 남김."""
    _record(retries=retries, drop_reason=drop_reason)
    changes = ", ".join(f"{change.law_name}({change.document_id}) {change.serial_number}" for change in request.changes)
    logger.error("법령 변경을 BE로 보내지 못함: %s (재시도 %d회, 변경 %d건: %s)", reason, retries,
                 len(request.changes), changes)


def to_callback_request(changes: list[LawChange]) -> LawChangeCallbackRequest | None:
    """변경 중 BE로 보낼 것만 골라 요청으로 만든다.

    Args:
        changes: 법령 점검이 찾은 변경.

    Returns:
        LawChangeCallbackRequest | None: 보낼 요청. 보낼 변경이 없으면 None.
    """
    applied = [_to_dto(change) for change in changes if change.kind is LawChangeKind.APPLIED]
    return LawChangeCallbackRequest(changes=applied) if applied else None


def _to_dto(change: LawChange) -> PublicLawChangeDto:
    """변경 하나를 BE 형식으로 바꾼다. 분야 이름은 ToolName 멤버 이름(예: CHILDREN)으로 보냄."""
    return PublicLawChangeDto(
        law_name=change.name,
        document_id=change.document_id,
        admrul=change.is_admrul,
        tool_name=ToolName(change.tool).name,
        serial_number=change.version.version,
        previous_serial_number=change.previous,
        revision_type=change.version.revision_type,
        enforce_date=_parse_date(change.version.enforce_date, change),
        issued_date=_parse_date(change.version.issued_date, change),
    )


def _parse_date(value: str | None, change: LawChange) -> date | None:
    """YYYYMMDD를 날짜로 바꾼다. 형식이 깨진 값은 비움 (값 하나로 묶음 전체가 거절되지 않게 함)."""
    if not value:
        return None
    try:
        return datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        logger.warning("법령 변경의 날짜 형식이 맞지 않아 비움 — %s %s: %r", change.name, change.version.version, value)
        return None
