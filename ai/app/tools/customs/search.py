"""품목분류 결정사례 조회와 HS별 세관장확인 요건 조회. 조회는 "비슷한 사례 고르기"이지 판단이 아니다.

- CaseSearch: Tool이 쓰는 결정사례 조회 인터페이스.
  - ClipCaseSearch: 관세청 CLIP 결정사례를 검색어별로 받아 상품 용어와의 글자 유사도로 순위를 매긴다.
  - DatabaseFirstCaseSearch: 적재한 결정사례(hs_cases)를 벡터로 먼저 찾고, 없으면 CLIP으로. case_search()가 만듦.
- RequirementLookup: HS 10자리로 세관장확인 대상 법령·요건확인기관·제출 서류를 조회한다.
  - GwRequirementLookup: 관세청 세관장확인대상물품 GW(공공데이터포털 키 필요). requirement_lookup()이 DB 캐시를 붙여 만듦.
- 근거 법령(관세법·고시·대외무역법 시행령)은 기준일별로 캐시한다(evidence_loader).
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from ...clients.customs import CLIPClient, CustomsGwClient
from ...schemas.clients.customs_request import CLIPSearchRequest, CustomsGwConfirmationRequest
from ...schemas.clients.customs_response import CLIPCase
from ..common.law import KST, CachedLoader, EvidenceUnavailable, LawApiClients
from ..common.ranking import rank_rows
from .evidence import CustomsEvidence, load_customs_evidence

logger = logging.getLogger(__name__)

_DESCRIPTION_LIMIT = 300
_REASON_LIMIT = 200
# DB 결정사례를 가까운 사례로 볼 코사인 거리 상한. None이면 거리와 상관없이 씀
_CASE_MAX_DISTANCE: float | None = None


@dataclass(frozen=True)
class HsCase:
    """품목분류 결정사례 하나. HS는 구성품별로 여러 개일 수 있다(숫자만, 10자리 또는 6자리)."""

    case_id: str
    hs_codes: tuple[str, ...]
    product_name: str
    description: str
    decision_reason: str
    enforce_date: str | None = None

    @classmethod
    def from_clip(cls, case: CLIPCase) -> "HsCase":
        """CLIP 결정사례를 조회 행으로 바꾼다.

        Args:
            case: CLIP 응답의 결정사례.

        Returns:
            HsCase: 조회 행.
        """
        # 문서 ID가 없으면 물품명만으로는 다른 사례와 겹칠 수 있어 HS까지 붙인다.
        case_id = case.doc_id or f"{case.product_name}#{'/'.join(case.hs_codes)}"
        return cls(case_id=case_id, hs_codes=tuple(case.hs_codes),
                   product_name=case.product_name, description=case.description,
                   decision_reason=case.decision_reason, enforce_date=case.enforce_date)

    def as_candidate(self) -> dict:
        """품목 선택 모델 입력. 긴 설명·결정 이유는 앞부분만 넣는다.

        Returns:
            dict: 사례 ID·HS·물품명·설명·결정 이유.
        """
        return {"case_id": self.case_id, "hs_codes": list(self.hs_codes), "product_name": self.product_name,
                "description": self.description[:_DESCRIPTION_LIMIT],
                "decision_reason": self.decision_reason[:_REASON_LIMIT]}


@dataclass(frozen=True)
class CaseCandidates:
    """조회 결과. failed_terms는 응답을 받지 못한 검색어(일부 실패는 나머지로 계속한다)."""

    cases: tuple[HsCase, ...]
    failed_terms: tuple[str, ...] = ()


class CaseSearch(Protocol):
    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates:
        """검색어로 결정사례를 찾아 상품 용어와 비슷한 순으로 고른다.

        Args:
            queries: 결정사례 검색어.
            terms: 순위를 매길 상품 용어.
            top_k: 돌려줄 최대 사례 수.

        Returns:
            CaseCandidates: 후보 사례와 실패한 검색어.
        """
        ...


def _clean_queries(queries: list[str]) -> list[str]:
    return list(dict.fromkeys(query.strip() for query in queries if query and query.strip()))


def _unique_cases(items: list[CLIPCase]) -> list[HsCase]:
    """받은 순서대로 결정사례를 합친다. HS 없는 사례는 뺌."""
    pool: dict[str, HsCase] = {}
    for item in items:
        case = HsCase.from_clip(item)
        if case.hs_codes:
            pool.setdefault(case.case_id, case)
    return list(pool.values())


def _rank_cases(items: list[CLIPCase], queries: list[str], terms: list[str], top_k: int) -> tuple[HsCase, ...]:
    """받은 결정사례를 합치고 상품 용어와 비슷한 순으로 top_k개를 고른다."""
    return tuple(rank_rows(
        _unique_cases(items), [*queries, *terms], top_k=top_k, key=lambda case: case.case_id,
        text=lambda case: f"{case.product_name} {case.description[:_DESCRIPTION_LIMIT]}",
        names=lambda case: [case.product_name],
    ))


class ClipCaseSearch:
    """관세청 CLIP 국내 품목분류 결정사례를 검색어별로 받아 순위를 매긴다.

    CLIP은 검색어가 물품명·설명에 들어 있는 사례를 최신순으로 준다(관련도순이 아니다).
    그래서 검색어마다 page_size건을 받아 합친 뒤, 상품 용어와의 글자 유사도로 다시 고른다.
    일부 검색어는 응답이 늦어 시간 초과가 나므로 검색어를 동시에 보내고, 일부 실패는 건너뛴다.

    Args:
        client_factory: CLIPClient를 만드는 함수(테스트는 Fake). 호출마다 새로 만들고 닫는다.
        page_size: 검색어당 받을 사례 수.
    """

    def __init__(self, client_factory: Callable[[], object] = CLIPClient, *, page_size: int = 30):
        self._client_factory = client_factory
        self._page_size = page_size

    def _fetch(self, query: str) -> list[CLIPCase]:
        """검색어 하나로 결정사례를 받는다. 클라이언트는 호출마다 열고 닫는다.

        Args:
            query: 검색어.

        Returns:
            list[CLIPCase]: 받은 결정사례.
        """
        client = self._client_factory()
        try:
            return client.fetch_parsed(CLIPSearchRequest(query=query, page_size=self._page_size)).items
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                close()

    def collect(self, queries: list[str]) -> tuple[list[CLIPCase], list[str], list[Exception]]:
        """검색어마다 동시에 받아 모은다. 검색어 하나의 시간 초과·오류는 나머지 검색어로 계속한다.

        Args:
            queries: CLIP에 보낼 검색어.

        Returns:
            tuple[list[CLIPCase], list[str], list[Exception]]: 받은 결정사례, 실패한 검색어, 실패 원인.
        """
        items: list[CLIPCase] = []
        failed: list[str] = []
        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = [(query, executor.submit(self._fetch, query)) for query in queries]
            for query, future in futures:
                try:
                    items.extend(future.result())
                except Exception as exc:
                    failed.append(query)
                    errors.append(exc)
        return items, failed, errors

    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates:
        """검색어로 사례를 받아 상품 용어와 비슷한 순으로 top_k개를 돌려준다.

        Args:
            queries: CLIP에 보낼 검색어(최대 3개 권장).
            terms: 순위를 매길 상품 용어(검색어·제품 종류·상품명 등).
            top_k: 돌려줄 최대 사례 수.

        Returns:
            CaseCandidates: 후보 사례와 실패한 검색어.

        Raises:
            Exception: 모든 검색어가 실패한 경우 마지막 오류를 그대로 올린다(호출자가 Tool 오류로 바꾼다).
        """
        queries = _clean_queries(queries)
        if not queries:
            return CaseCandidates(cases=())
        items, failed, errors = self.collect(queries)
        if len(failed) == len(queries):
            raise errors[-1]
        return CaseCandidates(cases=_rank_cases(items, queries, terms, top_k), failed_terms=tuple(failed))


class CaseDatabase(Protocol):
    def search_similar(self, text: str, *, top_k: int = 10) -> list[tuple[CLIPCase, float]]:
        """글과 의미가 비슷한 결정사례를 (사례, 코사인 거리)로 돌려준다."""
        ...


class DatabaseFirstCaseSearch:
    """적재한 결정사례를 벡터로 먼저 찾고, 가까운 사례가 없으면 CLIP API로 찾는다.

    적재 때 사례 전문을 임베딩했으므로 짧은 검색어 하나씩이 아니라 검색어·상품 용어를 이은 글 하나로 찾는다
    (짧은 검색어는 글자 모양이 비슷한 엉뚱한 사례로 끌려감, 2026-10-27 실측).
    DB 결과는 이미 의미가 가까운 순이라 그대로 쓴다(글자 유사도로 다시 고르면 정답이 밀려남, 2026-10-27 실측).
    DB 장애·임베딩 실패도 CLIP으로 돌린다. CLIP 결과만 글자 유사도로 고른다.

    Args:
        database: 결정사례 DB (app.db.ClipCaseDatabase).
        fallback: DB로 못 찾았을 때 쓸 CLIP 조회 경로.
        pool_size: DB에서 받을 사례 수. HS 없는 사례를 빼고 앞에서 top_k개를 쓴다.
        max_distance: 이 코사인 거리 이하만 가까운 사례로 봄. None이면 거리와 상관없이 씀.
    """

    def __init__(self, database: CaseDatabase, fallback: ClipCaseSearch, *, pool_size: int = 30,
                 max_distance: float | None = None):
        self._database = database
        self._fallback = fallback
        self._pool_size = pool_size
        self._max_distance = max_distance

    def _near(self, text: str) -> list[CLIPCase]:
        """DB에서 가까운 사례를 찾는다. 실패하면 빈 목록."""
        try:
            hits = self._database.search_similar(text, top_k=self._pool_size)
        except Exception as exc:  # DB 장애·임베딩 실패는 CLIP으로 대신함
            logger.warning("결정사례 DB 조회 실패 — CLIP으로 찾음: %s", type(exc).__name__)
            return []
        return [case for case, distance in hits if self._max_distance is None or distance <= self._max_distance]

    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates:
        """DB를 먼저 보고 가까운 순으로 top_k개를 쓴다. 가까운 사례가 없으면 검색어로 CLIP에서 받아 고른다.

        Args:
            queries: 결정사례 검색어.
            terms: 순위를 매길 상품 용어. DB 검색 글에도 넣음.
            top_k: 돌려줄 최대 사례 수.

        Returns:
            CaseCandidates: 후보 사례와 CLIP에서 실패한 검색어.

        Raises:
            Exception: DB로 못 찾았고 CLIP 검색어도 전부 실패한 경우.
        """
        queries = _clean_queries(queries)
        if not queries:
            return CaseCandidates(cases=())
        near = _unique_cases(self._near("\n".join(_clean_queries([*queries, *terms]))))
        if near:
            return CaseCandidates(cases=tuple(near[:top_k]))
        items, failed, errors = self._fallback.collect(queries)
        if len(failed) == len(queries):
            raise errors[-1]
        return CaseCandidates(cases=_rank_cases(items, queries, terms, top_k), failed_terms=tuple(failed))


@dataclass(frozen=True)
class Requirement:
    """HS 하나에 걸리는 세관장확인 요건 한 건(GW 응답 한 행)."""

    hs_code: str
    law_name: str
    agency: str | None = None
    document: str | None = None
    apply_start_date: str | None = None


class RequirementLookup(Protocol):
    def lookup(self, hs_code: str) -> list[Requirement]:
        """HS 하나의 세관장확인 요건을 조회한다.

        Args:
            hs_code: HS 10자리.

        Returns:
            list[Requirement]: 요건. 없으면 빈 목록.
        """
        ...


class GwRequirementLookup:
    """관세청 세관장확인대상물품 GW로 HS 10자리의 수입 요건을 조회한다. HS별로 캐시한다.

    빈 목록은 통관 단계의 세관장확인이 없다는 뜻일 뿐, 국내 판매 규제가 없다는 뜻은 아니다.

    Args:
        service_key: 공공데이터포털 서비스 키. 빈 값이면 조회할 수 없다(EvidenceUnavailable).
        ttl_seconds: HS별 캐시 유지 시간.
        clock: 현재 시각 함수. 테스트에서 시간을 흘릴 때 주입.
        client_factory: 서비스 키로 GW 클라이언트를 만드는 함수(테스트는 Fake).
    """

    def __init__(self, service_key: str | None, *, ttl_seconds: float = 6 * 3600,
                 clock: Callable[[], float] = time.monotonic,
                 client_factory: Callable[[str], object] = CustomsGwClient):
        self._service_key = service_key
        self._ttl = ttl_seconds
        self._clock = clock
        self._client_factory = client_factory
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, list[Requirement]]] = {}

    def lookup(self, hs_code: str) -> list[Requirement]:
        """HS 하나의 세관장확인 요건을 조회한다. 캐시가 있으면 그대로 돌려준다.

        Args:
            hs_code: HS 10자리.

        Returns:
            list[Requirement]: 요건. 없으면 빈 목록.

        Raises:
            EvidenceUnavailable: 서비스 키가 없는 경우.
        """
        if not self._service_key:
            raise EvidenceUnavailable("세관장확인 GW 서비스 키(DATA_GO_KR_KEY)가 없어 요건을 조회하지 못했습니다.")
        with self._lock:
            cached = self._cache.get(hs_code)
            if cached is not None and self._clock() - cached[0] < self._ttl:
                return cached[1]
        client = self._client_factory(self._service_key)
        try:
            response = client.fetch_parsed(CustomsGwConfirmationRequest(hs_code=hs_code))
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                close()
        requirements = [Requirement(hs_code=hs_code, law_name=item.law_name, agency=item.req_agency_name,
                                    document=item.req_document_name, apply_start_date=item.apply_start_date)
                        for item in response.items if item.law_name]
        with self._lock:
            self._cache[hs_code] = (self._clock(), requirements)
        return requirements


def _load_on_demand(as_of: date) -> CustomsEvidence:
    """조회할 때만 법제처 조회 객체(DB 캐시 먼저, 없으면 API)를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다.

    Args:
        as_of: 기준일.

    Returns:
        CustomsEvidence: 기준일 근거 묶음.
    """
    from ...config import get_settings
    from ...db import open_law_fetchers

    clients = LawApiClients(*open_law_fetchers(get_settings().law_oc))
    try:
        return load_customs_evidence(clients, as_of)
    finally:
        clients.close()


def evidence_loader() -> Callable[[], CustomsEvidence]:
    """기준일(한국 날짜)의 통관 근거를 돌려주는 함수를 만든다. 법제처 응답은 DB 캐시를 먼저 봄.

    기준일별 캐시는 함수마다 따로 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        Callable[[], CustomsEvidence]: 부를 때 오늘 기준 근거를 돌려주는 함수.
    """
    loader = CachedLoader(_load_on_demand)
    return lambda: loader.load(datetime.now(KST).date())


def case_search() -> ClipCaseSearch | DatabaseFirstCaseSearch:
    """결정사례 조회 경로를 만든다. DB에 적재한 사례를 먼저 보고, 없으면 CLIP.

    Returns:
        ClipCaseSearch | DatabaseFirstCaseSearch: DATABASE_URL이 없으면 CLIP만 쓰는 조회 경로.
    """
    from ...clients.llm.embedding import embed_text_sync
    from ...config import get_settings
    from ...db import ClipCaseDatabase, DatabaseNotConfiguredError, get_session_factory

    try:
        session_factory = get_session_factory()
    except DatabaseNotConfiguredError:
        return ClipCaseSearch()
    database = ClipCaseDatabase(session_factory, embed_query=embed_text_sync,
                                embedding_model=get_settings().embedding_model)
    return DatabaseFirstCaseSearch(database, ClipCaseSearch(), max_distance=_CASE_MAX_DISTANCE)


def requirement_lookup() -> GwRequirementLookup:
    """세관장확인 요건 조회 경로를 만든다. GW 응답은 DB 캐시를 먼저 봄.

    키는 설정의 DATA_GO_KR_KEY(필수). HS별 캐시는 객체 안에 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        GwRequirementLookup: 조회할 때 GW 조회 객체를 열고 닫는 요건 조회 경로.
    """
    from ...config import get_settings
    from ...db import open_customs_gw_fetcher

    return GwRequirementLookup(get_settings().data_go_kr_key, client_factory=open_customs_gw_fetcher)
