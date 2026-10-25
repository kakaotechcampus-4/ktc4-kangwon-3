"""법제처 조회용 DB 우선 조회 객체 묶음과 법령 점검 스케줄러.

Tool과 스케줄러가 같은 캐시 이름·같은 클라이언트 설정을 쓰도록 조회 객체를 한 곳(build_law_fetchers)에서 만든다.
스케줄러는 근거 문서마다 현행·시행예정 버전 목록을 새로 받고, 그 버전들의 본문을 미리 받아 둔다.
그래서 시행일이 되면 Tool은 외부 호출 없이 DB에서 새 버전을 고른다.
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import NamedTuple, Protocol

from sqlalchemy.orm import Session

from ..clients.law import AdmrulSearchClient, AdmrulTextClient, EflawSearchClient, LawTextClient
from ..config import LAW_REFRESH_AT, LAW_SEARCH_RECHECK_SECONDS
from ..schemas.clients.law_request import LawSearchRequest, LawTextRequest
from ..schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawSearchResponse, LawTextResponse,
)
from .fetchers import ScheduledFetcher

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


class LawSourceLike(Protocol):
    """점검할 근거 문서 하나. app.tools.common.law_sources.LawSource와 같은 모양."""

    name: str
    document_id: str
    is_admrul: bool


@dataclass
class LawRefreshReport:
    """점검 결과.

    Attributes:
        checked: 점검한 문서 수.
        versions: 본문을 확보한 버전 수(현행 + 시행예정).
        failed: 실패한 문서 이름.
    """

    checked: int = 0
    versions: int = 0
    failed: list[str] = field(default_factory=list)


def refresh_laws(fetchers: LawFetchers, sources: Iterable[LawSourceLike]) -> LawRefreshReport:
    """근거 문서마다 현행·시행예정 버전 목록을 새로 받고 그 본문을 확보한다.

    본문은 버전 번호가 키라 이미 DB에 있으면 다시 받지 않는다. 문서 하나가 실패해도 나머지는 계속한다.

    Args:
        fetchers: build_law_fetchers로 만든 조회 객체.
        sources: 점검할 근거 문서.

    Returns:
        LawRefreshReport: 점검 결과.
    """
    report = LawRefreshReport()
    for source in sources:
        report.checked += 1
        request = LawSearchRequest(query=source.name, display=100)
        try:
            if source.is_admrul:
                found = fetchers.admrul_search.refresh(request)
                versions = [item.serial_number for item in found.items
                            if item.rule_id == source.document_id and item.serial_number]
                text = fetchers.admrul_text
            else:
                found = fetchers.law_search.refresh(request)
                versions = [item.mst for item in found.items if item.law_id == source.document_id and item.mst]
                text = fetchers.law_text
            if not versions:
                raise LookupError(f"검색 결과에 문서 ID {source.document_id}가 없음")
            for version in versions:
                text.fetch_parsed(LawTextRequest(mst=version))
            report.versions += len(versions)
        except Exception as e:  # 문서 하나의 실패는 나머지 점검을 막지 않음
            logger.warning("법령 점검 실패 — %s: %s: %s", source.name, type(e).__name__, e)
            report.failed.append(source.name)
    logger.info("법령 점검 완료 — 문서 %d개, 버전 %d개, 실패 %s",
                report.checked, report.versions, report.failed or "없음")
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
