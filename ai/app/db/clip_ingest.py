"""CLIP 품목분류 결정사례 적재.

국내 결정사례 전체(검색어 공백 " "로 전체 목록이 나옴)의 문서 ID를 모으고, DB에 없는 사례만
상세 전문을 받아 임베딩해 hs_cases에 저장한다. 묶음마다 커밋하므로 중간에 멈춰도 다시 돌리면 이어서 받는다.
"""

import logging
import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..clients.customs import CLIPClient, CLIPDetailClient
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


@dataclass
class ClipIngestReport:
    """적재 결과.

    Attributes:
        listed: 목록에서 찾은 문서 수.
        existing: 이미 DB에 있어 건너뛴 문서 수.
        saved: 새로 저장한 문서 수.
        failed: 상세를 받지 못한 문서 ID.
    """

    listed: int = 0
    existing: int = 0
    saved: int = 0
    failed: list[str] = field(default_factory=list)


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


def collect_doc_ids(search: CLIPClient, *, workers: int, sleep: Callable[[float], None] = time.sleep) -> list[str]:
    """국내 결정사례 전체의 문서 ID를 모은다.

    Args:
        search: CLIP 검색 클라이언트.
        workers: 동시 요청 수.
        sleep: 재시도 대기 함수.

    Returns:
        list[str]: 목록 순서대로, 중복을 뺀 문서 ID.

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
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rest = list(pool.map(page, range(2, pages + 1)))
    doc_ids = [item.doc_id for result in (first, *rest) for item in result.items if item.doc_id]
    return list(dict.fromkeys(doc_ids))


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
    sleep: Callable[[float], None] = time.sleep,
) -> ClipIngestReport:
    """DB에 없는 결정사례를 받아 임베딩해 저장한다.

    Args:
        search: CLIP 검색 클라이언트.
        detail: CLIP 상세 클라이언트.
        embed: 글 목록 → 벡터 목록 (utils.embedding.embed_texts_sync).
        embedding_model: 벡터를 만든 임베딩 모델 이름.
        session_factory: DB 세션을 만드는 함수.
        workers: 동시 요청 수.
        chunk_size: 한 번에 임베딩·커밋하는 사례 수.
        limit: 새로 받을 최대 사례 수(시험 적재용). None이면 전부.
        sleep: 재시도 대기 함수.

    Returns:
        ClipIngestReport: 적재 결과.
    """
    report = ClipIngestReport()
    doc_ids = collect_doc_ids(search, workers=workers, sleep=sleep)
    with session_factory() as session:
        existing = HsCaseRepository(session).list_doc_ids()
    new = [doc_id for doc_id in doc_ids if doc_id not in existing]
    todo = new[:limit]
    report.listed, report.existing = len(doc_ids), len(doc_ids) - len(new)
    logger.info("CLIP 목록 %d건, 이미 있음 %d건, 받을 것 %d건", report.listed, report.existing, len(todo))

    def fetch(doc_id: str) -> CLIPCase | None:
        try:
            return _retry(lambda: detail.fetch_parsed(CLIPDetailRequest(doc_id=doc_id)), sleep=sleep)
        except Exception as exc:
            logger.warning("CLIP 상세 실패 %s (%s)", doc_id, type(exc).__name__)
            return None

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
            logger.info("CLIP 적재 %d/%d (실패 %d)", start + len(chunk), len(todo), len(report.failed))
    return report
