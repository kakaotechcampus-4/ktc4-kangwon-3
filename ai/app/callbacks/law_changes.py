"""법령 점검이 찾은 변경을 BE로 보내는 형식으로 바꾼다 (#673).

보내는 건 근거로 쓰는 판이 바뀐 변경(APPLIED)만. 새 판 발표(ANNOUNCED)는 아직 시행 전이고,
건너뛴 판(SKIPPED)은 사람이 확인할 일이라 로그로만 남김.
"""

import logging
from datetime import date, datetime

from ..db import LawChange, LawChangeKind
from ..schemas.callback import LawChangeCallbackRequest, PublicLawChangeDto
from ..schemas.schemas import ToolName

logger = logging.getLogger(__name__)

_DATE_FORMAT = "%Y%m%d"


def to_callback_request(changes: list[LawChange], checked_on: date) -> LawChangeCallbackRequest | None:
    """변경 중 BE로 보낼 것만 골라 요청으로 만든다.

    Args:
        changes: 법령 점검이 찾은 변경.
        checked_on: 점검 기준일.

    Returns:
        LawChangeCallbackRequest | None: 보낼 요청. 보낼 변경이 없으면 None.
    """
    applied = [_to_dto(change) for change in changes if change.kind is LawChangeKind.APPLIED]
    return LawChangeCallbackRequest(checked_on=checked_on, changes=applied) if applied else None


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
