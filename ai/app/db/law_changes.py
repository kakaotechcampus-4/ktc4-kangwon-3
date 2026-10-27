"""법령 점검이 찾은 근거 문서 변경. 받는 쪽(로그·BE 알림)은 LawChangeSink로 끼운다."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class LawSourceLike(Protocol):
    """점검할 근거 문서 하나. app.tools.common.law_sources.LawSource와 같은 모양."""

    name: str
    document_id: str
    is_admrul: bool


class LawChangeKind(StrEnum):
    """변경 종류.

    Attributes:
        ANNOUNCED: 검색 목록에 새 판이 생김.
        APPLIED: 기준일에 적용되는 판이 바뀜.
        SKIPPED: 시행일이 됐지만 나중에 공포·발령된 판이 있어 쓰지 않음. 사람이 확인할 것.
    """

    ANNOUNCED = "announced"
    APPLIED = "applied"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class LawVersion:
    """검색 목록의 판 하나.

    Attributes:
        version: 법령일련번호(MST) 또는 행정규칙일련번호.
        enforce_date: 시행일(YYYYMMDD).
        issued_date: 공포일·발령일(YYYYMMDD).
    """

    version: str
    enforce_date: str | None
    issued_date: str | None


@dataclass(frozen=True)
class LawChange:
    """근거 문서 변경 하나.

    Attributes:
        kind: 변경 종류.
        name: 문서 이름.
        document_id: 법령ID 또는 행정규칙ID.
        is_admrul: 행정규칙이면 True.
        version: 해당 판.
        previous: APPLIED일 때 이전에 적용되던 판 번호.
    """

    kind: LawChangeKind
    name: str
    document_id: str
    is_admrul: bool
    version: LawVersion
    previous: str | None = None


LawChangeSink = Callable[[list[LawChange]], None]
VersionSelector = Callable[[LawSourceLike, Any, date], str | None]


def versions_of(source: LawSourceLike, response: Any) -> list[LawVersion]:
    """검색 응답에서 그 문서의 판만 꺼낸다.

    Args:
        source: 근거 문서.
        response: 법령(LawSearchResponse) 또는 행정규칙(AdmrulSearchResponse) 검색 응답.

    Returns:
        list[LawVersion]: 목록 순서대로의 판.
    """
    if source.is_admrul:
        return [LawVersion(item.serial_number, item.enforce_date, item.issue_date) for item in response.items
                if item.rule_id == source.document_id and item.serial_number]
    return [LawVersion(item.mst, item.enforce_date, item.promulgate_date) for item in response.items
            if item.law_id == source.document_id and item.mst]


def detect_changes(source: LawSourceLike, before: Any | None, after: Any, *, today: date,
                   select: VersionSelector | None) -> list[LawChange]:
    """어제 저장된 검색 목록과 오늘 받은 목록을 비교한다.

    Args:
        source: 근거 문서.
        before: DB에 있던 검색 응답. 처음 점검이면 None(새 판 발표는 내지 않음).
        after: 새로 받은 검색 응답.
        today: 점검 기준일(KST).
        select: (문서, 검색 응답, 기준일) → 적용 판 번호. None이면 새 판 발표만 본다.

    Returns:
        list[LawChange]: 찾은 변경.
    """
    found = versions_of(source, after)

    def change(kind: LawChangeKind, version: LawVersion, previous: str | None = None) -> LawChange:
        return LawChange(kind, source.name, source.document_id, source.is_admrul, version, previous)

    changes = []
    if before is not None:
        known = set(versions_of(source, before))
        changes += [change(LawChangeKind.ANNOUNCED, version) for version in found if version not in known]
    if select is None:
        return changes
    yesterday, day = (today - timedelta(days=1)).strftime("%Y%m%d"), today.strftime("%Y%m%d")
    previous = select(source, after if before is None else before, today - timedelta(days=1))
    current = select(source, after, today)
    if current is not None and previous is not None and current != previous:
        applied = max((version for version in found
                       if version.version == current and (version.enforce_date or "") <= day),
                      key=lambda version: version.enforce_date or "")
        changes.append(change(LawChangeKind.APPLIED, applied, previous))
    changes += [change(LawChangeKind.SKIPPED, version) for version in found
                if yesterday < (version.enforce_date or "") <= day and version.version != current]
    return changes


def log_law_changes(changes: list[LawChange]) -> None:
    """변경을 로그로 남긴다. BE 알림 방식이 정해지기 전 기본 받는 쪽.

    Args:
        changes: 찾은 변경.
    """
    for change in changes:
        log = logger.warning if change.kind is LawChangeKind.SKIPPED else logger.info
        log("법령 변경 %s — %s %s (시행 %s, 공포·발령 %s, 이전 %s)", change.kind.value, change.name,
            change.version.version, change.version.enforce_date, change.version.issued_date, change.previous or "-")
