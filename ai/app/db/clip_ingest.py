"""CLIP 품목분류 결정사례 적재.

국내 결정사례 전체(검색어 공백 " "로 전체 목록이 나옴)의 문서 ID를 모으고, DB에 없는 사례만
상세 전문을 받아 임베딩해 hs_cases에 저장한다. 묶음마다 커밋하므로 중간에 멈춰도 다시 돌리면 이어서 받는다.
raw_dir을 주면 상세 원문도 문서마다 raw.html·parsed.json·meta.json으로 남긴다.
"""

import asyncio
import json
import logging
import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, time as clock_time, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from sqlalchemy.orm import Session

from ..clients.customs import CLIPClient, CLIPDetailClient
from ..config import CLIP_INGEST_WEEKLY_AT
from ..schemas.clients.customs_request import CLIPDetailRequest, CLIPSearchRequest
from ..schemas.clients.customs_response import CLIPCase, CLIPSearchResponse
from .models.hs_case import HsCase
from .repositories.hs_case import HsCaseRepository

logger = logging.getLogger(__name__)

# 검색어 공백이면 국내 결정사례 전체가 나옴 (2026-10-25 실측 54,303건)
ALL_CASES_QUERY = " "
PAGE_SIZE = 100
# CLIP은 간헐적으로 빈 페이지·오류를 줘서 다시 받음
RETRIES = 3
# 목록 진행 상황을 남기는 간격(페이지)
LOG_EVERY_PAGES = 50


@dataclass
class ClipIngestReport:
    """적재 결과.

    Attributes:
        listed: 목록에서 찾은 문서 수.
        existing: 이미 DB에 있어 건너뛴 문서 수.
        saved: 새로 저장한 문서 수.
        removed: 목록에서 사라져 지운 문서 수.
        failed: 상세를 받지 못한 문서 ID.
    """

    listed: int = 0
    existing: int = 0
    saved: int = 0
    removed: int = 0
    failed: list[str] = field(default_factory=list)


class CaseIds(NamedTuple):
    """CLIP 목록에서 모은 문서 ID.

    Attributes:
        doc_ids: 목록 순서대로, 중복을 뺀 문서 ID.
        total: CLIP이 알려 준 전체 건수.
    """

    doc_ids: list[str]
    total: int


def case_text(case: CLIPCase) -> str:
    """결정사례의 임베딩 입력. 품명·물품설명·결정사유 전문 (2026-10-25 실측에서 가장 나음).

    Args:
        case: 결정사례.

    Returns:
        str: 줄바꿈으로 이은 글.
    """
    return "\n".join(part.strip() for part in (case.product_name, case.description, case.decision_reason)
                     if part and part.strip())


def _retry(call: Callable[[], CLIPSearchResponse | CLIPCase], *, sleep: Callable[[float], None]):
    for attempt in range(RETRIES):
        try:
            return call()
        except Exception:
            if attempt == RETRIES - 1:
                raise
            sleep(3 * (attempt + 1))


def collect_doc_ids(search: CLIPClient, *, workers: int, sleep: Callable[[float], None] = time.sleep) -> CaseIds:
    """국내 결정사례 전체의 문서 ID를 모은다.

    Args:
        search: CLIP 검색 클라이언트.
        workers: 동시 요청 수.
        sleep: 재시도 대기 함수.

    Returns:
        CaseIds: 문서 ID와 전체 건수.

    Raises:
        RuntimeError: 재시도 뒤에도 페이지가 비어 있는 경우(목록 불완전).
    """
    def page(number: int) -> CLIPSearchResponse:
        def call():
            result = search.fetch_parsed(CLIPSearchRequest(query=ALL_CASES_QUERY, page=number, page_size=PAGE_SIZE))
            if not result.items:
                raise RuntimeError(f"CLIP 목록 {number}페이지가 비어 있습니다.")
            return result
        return _retry(call, sleep=sleep)

    first = page(1)
    pages = math.ceil(first.total_count / PAGE_SIZE)
    logger.info("CLIP 목록 받는 중 — 전체 %d건, %d페이지", first.total_count, pages)
    rest = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for number, result in enumerate(pool.map(page, range(2, pages + 1)), start=2):
            rest.append(result)
            if number % LOG_EVERY_PAGES == 0:
                logger.info("CLIP 목록 %d/%d페이지", number, pages)
    doc_ids = [item.doc_id for result in (first, *rest) for item in result.items if item.doc_id]
    return CaseIds(list(dict.fromkeys(doc_ids)), first.total_count)


def fetch_detail(detail: CLIPDetailClient, doc_id: str, raw_dir: Path | None) -> CLIPCase:
    """결정사례 상세를 받는다. raw_dir이 있으면 원문을 먼저 저장해 파싱이 실패해도 남긴다.

    Args:
        detail: CLIP 상세 클라이언트.
        doc_id: 문서 ID.
        raw_dir: 원문 저장 폴더. None이면 저장 안 함.

    Returns:
        CLIPCase: 결정사례.

    Raises:
        RuntimeError: 상세가 비어 있는 경우.
        httpx.HTTPError: 요청 실패.
    """
    request = CLIPDetailRequest(doc_id=doc_id)
    if raw_dir is None:
        return detail.fetch_parsed(request)
    raw = detail.fetch_raw(request)
    case_dir = raw_dir / doc_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "raw.html").write_text(raw.text, encoding="utf-8")
    (case_dir / "meta.json").write_text(json.dumps({
        "request": request.model_dump(), "url": str(raw.request.url), "status_code": raw.status_code,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # BaseClient.parse 공개 전까지 내부 변환 메서드 사용
    case = detail._parse(raw)
    (case_dir / "parsed.json").write_text(case.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return case


def ingest_clip_cases(
    *,
    search: CLIPClient,
    detail: CLIPDetailClient,
    embed: Callable[[list[str]], list[list[float]]],
    embedding_model: str,
    session_factory: Callable[[], Session],
    workers: int = 4,
    chunk_size: int = 100,
    limit: int | None = None,
    raw_dir: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ClipIngestReport:
    """DB에 없는 결정사례를 받아 임베딩해 저장한다.

    Args:
        search: CLIP 검색 클라이언트.
        detail: CLIP 상세 클라이언트.
        embed: 글 목록 → 벡터 목록 (clients.llm.embedding.embed_texts_sync).
        embedding_model: 벡터를 만든 임베딩 모델 이름.
        session_factory: DB 세션을 만드는 함수.
        workers: 동시 요청 수.
        chunk_size: 한 번에 임베딩·커밋하는 사례 수.
        limit: 새로 받을 최대 사례 수(시험 적재용). None이면 전부.
        raw_dir: 상세 원문 저장 폴더. None이면 저장 안 함.
        sleep: 재시도 대기 함수.

    Returns:
        ClipIngestReport: 적재 결과.
    """
    report = ClipIngestReport()
    doc_ids, total = collect_doc_ids(search, workers=workers, sleep=sleep)
    with session_factory() as session:
        existing = HsCaseRepository(session).list_doc_ids()
        gone = existing - set(doc_ids)
        if gone and len(doc_ids) < total:
            logger.warning("CLIP 목록이 전체보다 적어(%d/%d건) 사라진 사례 %d건을 지우지 않음",
                           len(doc_ids), total, len(gone))
        elif gone:
            report.removed = HsCaseRepository(session).delete_many(sorted(gone))
            session.commit()
    new = [doc_id for doc_id in doc_ids if doc_id not in existing]
    todo = new[:limit]
    report.listed, report.existing = len(doc_ids), len(doc_ids) - len(new)
    logger.info("CLIP 목록 %d건, 이미 있음 %d건, 받을 것 %d건", report.listed, report.existing, len(todo))

    def fetch(doc_id: str) -> CLIPCase | None:
        try:
            return _retry(lambda: fetch_detail(detail, doc_id, raw_dir), sleep=sleep)
        except Exception as exc:
            logger.warning("CLIP 상세 실패 %s (%s)", doc_id, type(exc).__name__)
            return None

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(todo), chunk_size):
            chunk = todo[start:start + chunk_size]
            cases = []
            for doc_id, case in zip(chunk, pool.map(fetch, chunk)):
                if case is None:
                    report.failed.append(doc_id)
                else:
                    cases.append(case)
            if not cases:
                continue
            vectors = embed([case_text(case) for case in cases])
            with session_factory() as session:
                HsCaseRepository(session).upsert_many([
                    HsCase(**case.model_dump(), embedding=vector, embedding_model=embedding_model)
                    for case, vector in zip(cases, vectors)])
                session.commit()
            report.saved += len(cases)
            done = start + len(chunk)
            rate = done / max(time.monotonic() - started, 1e-3)
            logger.info("CLIP 적재 %d/%d (실패 %d) — %.1f건/초, 남은 시간 약 %d분", done, len(todo),
                        len(report.failed), rate, (len(todo) - done) / rate / 60)
    return report


KST = timezone(timedelta(hours=9))


def run_scheduled_clip_ingest(session_factory: Callable[[], Session], *, embed: Callable[[list[str]], list[list[float]]],
                              embedding_model: str) -> ClipIngestReport | None:
    """주간 적재 한 번. hs_cases가 비어 있으면(초기 적재 전) 하지 않는다.

    Args:
        session_factory: DB 세션을 만드는 함수.
        embed: 글 목록 → 벡터 목록.
        embedding_model: 벡터를 만든 임베딩 모델 이름.

    Returns:
        ClipIngestReport | None: 적재 결과. 건너뛰면 None.
    """
    with session_factory() as session:
        if not HsCaseRepository(session).list_doc_ids():
            logger.warning("CLIP 주간 적재 건너뜀 — hs_cases가 비어 있음 (초기 적재는 cli clip-ingest로)")
            return None
    search, detail = CLIPClient(), CLIPDetailClient()
    try:
        report = ingest_clip_cases(search=search, detail=detail, embed=embed, embedding_model=embedding_model,
                                   session_factory=session_factory)
    finally:
        search.close()
        detail.close()
    logger.info("CLIP 주간 적재 — 새로 저장 %d건, 삭제 %d건, 실패 %d건", report.saved, report.removed, len(report.failed))
    return report


def seconds_until_weekly(now: datetime, at: tuple[int, int, int]) -> float:
    """now 다음에 오는 at(요일·시·분, 월=0)까지 남은 초. now와 같은 시간대로 계산한다.

    Args:
        now: 현재 시각(시간대 포함).
        at: (요일, 시, 분).

    Returns:
        float: 남은 초. 이미 지났거나 정각이면 다음 주 그 시각까지.
    """
    weekday, hour, minute = at
    target = datetime.combine(now.date(), clock_time(hour, minute), tzinfo=now.tzinfo)
    target += timedelta(days=(weekday - now.weekday()) % 7)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


async def run_weekly_clip_ingest(ingest: Callable[[], object], *, at: tuple[int, int, int] = CLIP_INGEST_WEEKLY_AT,
                                 now: Callable[[], datetime] = lambda: datetime.now(KST),
                                 sleep: Callable[[float], object] = asyncio.sleep) -> None:
    """매주 at(KST)에 결정사례 적재를 실행한다. 기동 직후에는 하지 않는다. 취소될 때까지 돈다.

    Args:
        ingest: 적재 함수(보통 run_scheduled_clip_ingest를 묶은 것). 동기라 스레드에서 실행한다.
        at: 매주 실행할 (요일, 시, 분).
        now: 현재 시각. 테스트용.
        sleep: 대기 함수. 테스트용.
    """
    while True:
        await sleep(seconds_until_weekly(now(), at))
        try:
            await asyncio.to_thread(ingest)
        except Exception:
            logger.exception("CLIP 주간 적재 실패")

