"""법제처 조회용 DB 우선 조회 객체 묶음과 법령 점검 스케줄러.

Tool과 스케줄러가 같은 캐시 이름·같은 클라이언트 설정을 쓰도록 조회 객체를 한 곳(build_law_fetchers)에서 만든다.
스케줄러는 근거 문서마다 현행·시행예정 버전 목록을 새로 받고, 그 버전들의 본문을 미리 받아 둔다.
그래서 시행일이 되면 Tool은 외부 호출 없이 DB에서 새 버전을 고른다.
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import NamedTuple

from sqlalchemy.orm import Session

from ..clients.law import AdmrulSearchClient, AdmrulTextClient, EflawSearchClient, LawTextClient
from ..config import LAW_REFRESH_AT, LAW_SEARCH_RECHECK_SECONDS
from ..schemas.clients.law_request import LawSearchRequest, LawTextRequest
from ..schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawSearchResponse, LawTextResponse,
)
from .engine import get_session_factory
from .errors import DatabaseNotConfiguredError
from .fetchers import ScheduledFetcher
from .law_changes import LawChange, LawChangeSink, LawSourceLike, VersionSelector, detect_changes, versions_of

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class LawFetchers(NamedTuple):
    """법제처 조회 4종의 DB 우선 조회 객체. LawApiClients 자리에 그대로 넣을 수 있는 순서·이름."""

    law_search: ScheduledFetcher[LawSearchResponse]
    law_text: ScheduledFetcher[LawTextResponse]
    admrul_search: ScheduledFetcher[AdmrulSearchResponse]
    admrul_text: ScheduledFetcher[AdmrulTextResponse]

    def close(self) -> None:
        """클라이언트 연결을 모두 정리한다."""
        for fetcher in self:
            fetcher.close()


def build_law_fetchers(oc: str, session_factory: Callable[[], Session] | None) -> LawFetchers:
    """법제처 조회 4종의 DB 우선 조회 객체를 만든다.

    법령 검색은 시행법령 검색(현행·시행예정만)으로 받는다. 시행 예정 버전이 목록에 있어야
    시행일에 select_version이 외부 호출 없이 새 버전을 고른다.

    Args:
        oc: 법제처 OC.
        session_factory: DB 세션을 만드는 함수. None이면 캐시 없이 클라이언트만 쓴다.

    Returns:
        LawFetchers: 검색은 점검 기한(LAW_SEARCH_RECHECK_SECONDS), 본문은 영구 보관.
    """
    recheck = timedelta(seconds=LAW_SEARCH_RECHECK_SECONDS)
    return LawFetchers(
        law_search=ScheduledFetcher(
            EflawSearchClient(oc, include_history=False), name="law.eflaw_search",
            response_type=LawSearchResponse, recheck_after=recheck, session_factory=session_factory),
        law_text=ScheduledFetcher(
            LawTextClient(oc), name="law.text",
            response_type=LawTextResponse, recheck_after=None, session_factory=session_factory),
        admrul_search=ScheduledFetcher(
            AdmrulSearchClient(oc), name="admrul.search",
            response_type=AdmrulSearchResponse, recheck_after=recheck, session_factory=session_factory),
        admrul_text=ScheduledFetcher(
            AdmrulTextClient(oc), name="admrul.text",
            response_type=AdmrulTextResponse, recheck_after=None, session_factory=session_factory),
    )


def open_law_fetchers(oc: str) -> LawFetchers:
    """Tool이 쓰는 법제처 조회 객체를 공용 DB에 연결해 만든다. 다 쓰면 close()로 닫는다.

    Args:
        oc: 법제처 OC.

    Returns:
        LawFetchers: DATABASE_URL이 없으면 캐시 없이 클라이언트만 쓰는 조회 객체.

    Raises:
        ConfigError: DB 엔진을 만들 수 없는 경우.
    """
    try:
        session_factory = get_session_factory()
    except DatabaseNotConfiguredError:
        session_factory = None
    return build_law_fetchers(oc, session_factory)


@dataclass
class LawRefreshReport:
    """점검 결과.

    Attributes:
        checked: 점검한 문서 수.
        versions: 본문을 확보한 버전 수(현행 + 시행예정).
        failed: 실패한 문서 이름.
        changes: 어제 목록과 비교해 찾은 변경.
    """

    checked: int = 0
    versions: int = 0
    failed: list[str] = field(default_factory=list)
    changes: list[LawChange] = field(default_factory=list)


def refresh_laws(fetchers: LawFetchers, sources: Iterable[LawSourceLike], *, select: VersionSelector | None = None,
                 on_change: LawChangeSink | None = None, today: date | None = None) -> LawRefreshReport:
    """근거 문서마다 현행·시행예정 버전 목록을 새로 받고 그 본문을 확보한다.

    본문은 버전 번호가 키라 이미 DB에 있으면 다시 받지 않는다. 문서 하나가 실패해도 나머지는 계속한다.
    덮어쓰기 전 DB 목록과 비교해 변경을 찾고, 있으면 on_change에 한 번에 넘긴다.

    Args:
        fetchers: build_law_fetchers로 만든 조회 객체.
        sources: 점검할 근거 문서.
        select: (문서, 검색 응답, 기준일) → 적용 판 번호. None이면 새 판 발표만 찾는다.
        on_change: 변경을 받는 함수. None이면 보고서에만 남긴다.
        today: 기준일. None이면 오늘(KST).

    Returns:
        LawRefreshReport: 점검 결과.
    """
    today = today or datetime.now(KST).date()
    report = LawRefreshReport()
    for source in sources:
        report.checked += 1
        request = LawSearchRequest(query=source.name, display=100)
        search = fetchers.admrul_search if source.is_admrul else fetchers.law_search
        text = fetchers.admrul_text if source.is_admrul else fetchers.law_text
        try:
            before = search.cached(request)
            found = search.refresh(request, accept=lambda response: bool(versions_of(source, response)))
            versions = [version.version for version in versions_of(source, found)]
            for version in versions:
                text.fetch_parsed(LawTextRequest(mst=version))
            report.versions += len(versions)
            report.changes += detect_changes(source, before, found, today=today, select=select)
        except Exception as e:  # 문서 하나의 실패는 나머지 점검을 막지 않음
            logger.warning("법령 점검 실패 — %s: %s: %s", source.name, type(e).__name__, e)
            report.failed.append(source.name)
    logger.info("법령 점검 완료 — 문서 %d개, 버전 %d개, 변경 %d건, 실패 %s",
                report.checked, report.versions, len(report.changes), report.failed or "없음")
    if report.changes and on_change is not None:
        try:
            on_change(report.changes)
        except Exception:
            logger.exception("법령 변경 전달 실패")
    return report


def seconds_until(now: datetime, at: tuple[int, int]) -> float:
    """now 다음에 오는 at(시·분) 시각까지 남은 초. now와 같은 시간대로 계산한다.

    Args:
        now: 현재 시각(시간대 포함).
        at: (시, 분).

    Returns:
        float: 남은 초. 이미 지났거나 정각이면 다음 날 그 시각까지.
    """
    target = datetime.combine(now.date(), time(*at), tzinfo=now.tzinfo)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_law_refresh(refresh: Callable[[], object], *, at: tuple[int, int] = LAW_REFRESH_AT,
                          now: Callable[[], datetime] = lambda: datetime.now(KST),
                          sleep: Callable[[float], object] = asyncio.sleep) -> None:
    """기동 직후 한 번, 이후 매일 at(KST) 시각에 법령 점검을 실행한다. 취소될 때까지 돈다.

    Args:
        refresh: 점검 함수(보통 refresh_laws를 묶은 것). 동기라 스레드에서 실행한다.
        at: 매일 실행할 (시, 분).
        now: 현재 시각. 테스트용.
        sleep: 대기 함수. 테스트용.
    """
    while True:
        try:
            await asyncio.to_thread(refresh)
        except Exception:
            logger.exception("법령 점검 실행 실패")
        await sleep(seconds_until(now(), at))
