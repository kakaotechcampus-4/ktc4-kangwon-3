"""품목분류 결정사례 조회와 HS별 세관장확인 요건 조회. 조회는 "비슷한 사례 고르기"이지 판단이 아니다.

- CaseSearch: Tool이 쓰는 결정사례 조회 인터페이스.
  - ClipCaseSearch: 지금 쓰는 경로. 관세청 CLIP 결정사례를 검색어별로 받아 상품 용어와의 글자 유사도로 순위를 매긴다.
  - DatabaseCaseSearch: hs_cases 테이블(결정사례 + 임베딩) 적재 후 벡터 조회로 바꿀 자리(스텁).
- RequirementLookup: HS 10자리로 세관장확인 대상 법령·요건확인기관·제출 서류를 조회한다.
  - GwRequirementLookup: 관세청 세관장확인대상물품 GW(공공데이터포털 키 필요).
- 근거 법령(관세법·고시·대외무역법 시행령)은 기준일별로 캐시한다(law_api_evidence_loader).
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from ...clients.customs import CLIPClient, CustomsGwClient
from ...schemas.clients.customs_request import CLIPSearchRequest, CustomsGwConfirmationRequest
from ...schemas.clients.customs_response import CLIPCase
from ..common.law import CachedLoader, EvidenceUnavailable, LawApiClients
from ..common.ranking import rank_rows
from .evidence import CustomsEvidence, load_customs_evidence

KST = timezone(timedelta(hours=9))
_DESCRIPTION_LIMIT = 300
_REASON_LIMIT = 200


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
        # 문서 ID가 없으면 물품명만으로는 다른 사례와 겹칠 수 있어 HS까지 붙인다.
        case_id = case.doc_id or f"{case.product_name}#{'/'.join(case.hs_codes)}"
        return cls(case_id=case_id, hs_codes=tuple(case.hs_codes),
                   product_name=case.product_name, description=case.description,
                   decision_reason=case.decision_reason, enforce_date=case.enforce_date)

    def as_candidate(self) -> dict:
        """품목 선택 모델 입력. 긴 설명·결정 이유는 앞부분만 넣는다."""
        return {"case_id": self.case_id, "hs_codes": list(self.hs_codes), "product_name": self.product_name,
                "description": self.description[:_DESCRIPTION_LIMIT],
                "decision_reason": self.decision_reason[:_REASON_LIMIT]}


@dataclass(frozen=True)
class CaseCandidates:
    """조회 결과. failed_terms는 응답을 받지 못한 검색어(일부 실패는 나머지로 계속한다)."""

    cases: tuple[HsCase, ...]
    failed_terms: tuple[str, ...] = ()


class CaseSearch(Protocol):
    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates: ...


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
        client = self._client_factory()
        try:
            return client.fetch_parsed(CLIPSearchRequest(query=query, page_size=self._page_size)).items
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                close()

    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates:
        """검색어로 사례를 받아 상품 용어와 비슷한 순으로 top_k개를 돌려준다.

        Args:
            queries: CLIP에 보낼 검색어(최대 3개 권장).
            terms: 순위를 매길 상품 용어(검색어·제품 종류·상품명 등).

        Raises:
            Exception: 모든 검색어가 실패한 경우 마지막 오류를 그대로 올린다(호출자가 Tool 오류로 바꾼다).
        """
        queries = list(dict.fromkeys(query.strip() for query in queries if query and query.strip()))
        if not queries:
            return CaseCandidates(cases=())
        pool: dict[str, HsCase] = {}
        failed: list[str] = []
        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = [(query, executor.submit(self._fetch, query)) for query in queries]
            for query, future in futures:
                try:
                    items = future.result()
                except Exception as exc:  # 검색어 하나의 시간 초과·오류는 나머지 검색어로 계속한다.
                    failed.append(query)
                    errors.append(exc)
                    continue
                for item in items:
                    case = HsCase.from_clip(item)
                    if case.hs_codes:
                        pool.setdefault(case.case_id, case)
        if len(failed) == len(queries):
            raise errors[-1]
        ranked = rank_rows(
            pool.values(), [*queries, *terms], top_k=top_k, key=lambda case: case.case_id,
            text=lambda case: f"{case.product_name} {case.description[:_DESCRIPTION_LIMIT]}",
            names=lambda case: [case.product_name],
        )
        return CaseCandidates(cases=tuple(ranked), failed_terms=tuple(failed))


class DatabaseCaseSearch:
    """hs_cases 테이블(CLIP 결정사례 + 임베딩)에서 벡터 조회하는 경로. 적재가 끝나면 쓴다(스텁).

    HsCaseRepository.search_by_vector(app/repositories/customs.py)와 app.utils.embedding을 쓴다.
    Tool은 동기라 비동기 embed_text를 그대로 부를 수 없다. 같은 CaseCandidates를 돌려주면 CustomsTool은 바꾸지 않는다.

    Args:
        session_factory: app.database.get_session_factory()가 돌려주는 세션 팩토리.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def search(self, queries: list[str], terms: list[str], *, top_k: int) -> CaseCandidates:
        raise NotImplementedError("DB 결정사례 조회는 hs_cases 적재 후 구현합니다.")


@dataclass(frozen=True)
class Requirement:
    """HS 하나에 걸리는 세관장확인 요건 한 건(GW 응답 한 행)."""

    hs_code: str
    law_name: str
    agency: str | None = None
    document: str | None = None
    apply_start_date: str | None = None


class RequirementLookup(Protocol):
    def lookup(self, hs_code: str) -> list[Requirement]: ...


class GwRequirementLookup:
    """관세청 세관장확인대상물품 GW로 HS 10자리의 수입 요건을 조회한다. HS별로 캐시한다.

    빈 목록은 통관 단계의 세관장확인이 없다는 뜻일 뿐, 국내 판매 규제가 없다는 뜻은 아니다.

    Args:
        service_key: 공공데이터포털 서비스 키. 빈 값이면 조회할 수 없다(EvidenceUnavailable).
        ttl_seconds: HS별 캐시 유지 시간.
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
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다."""
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return load_customs_evidence(clients, as_of)
    finally:
        clients.close()


def law_api_evidence_loader() -> Callable[[], CustomsEvidence]:
    """기준일(한국 날짜)의 통관 근거를 법제처 API로 돌려주는 함수를 만든다.

    기준일별 캐시는 함수마다 따로 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        Callable[[], CustomsEvidence]: 부를 때 오늘 기준 근거를 돌려주는 함수.
    """
    loader = CachedLoader(_load_on_demand)
    return lambda: loader.load(datetime.now(KST).date())
