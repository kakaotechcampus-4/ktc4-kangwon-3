"""어린이제품 품목 조회. 조회는 "비슷한 품목 고르기"이지 판단이 아니다.

- ChildrenItemSearch: Tool이 쓰는 조회 인터페이스.
- LawApiItemSearch: 지금 쓰는 경로. 법제처 응답을 직접 읽어 품목 행을 만들고 기준일별로 캐시한다.
- DatabaseItemSearch: 적재 단계 파싱 에이전트가 품목표를 DB에 넣으면 쓸 경로(스텁).
"""

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from ..common.law import CachedLoader, DocRef, LawApiClients
from ..common.ranking import rank_rows
from .evidence import ChildrenEvidence, ChildrenItem, Definitions, load_children_evidence

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class ChildrenCandidates:
    """조회 결과. items는 상품과 비슷한 품목 행(terms가 비면 빈 목록)."""

    items: tuple[ChildrenItem, ...]
    common_standard: ChildrenItem
    definitions: Definitions
    rule: DocRef
    notice: DocRef
    documents: list[dict[str, str]] = field(default_factory=list)


class ChildrenItemSearch(Protocol):
    def catalog(self) -> list[str]: ...
    def search(self, terms: list[str], *, top_k: int) -> ChildrenCandidates: ...


class LawApiItemSearch:
    """법제처 API로 법·시행규칙·운용요령을 받아 품목 행을 만든다. 기준일(한국 날짜)별로 캐시한다.

    Args:
        loader: 기준일을 받아 ChildrenEvidence를 돌려주는 함수(보통 CachedLoader.load).
        as_of: 고정 기준일. None이면 호출 시점의 한국 날짜.
    """

    def __init__(self, loader, *, as_of: date | None = None):
        self._loader = loader
        self._as_of = as_of

    def evidence(self) -> ChildrenEvidence:
        return self._loader(self._as_of or datetime.now(KST).date())

    def catalog(self) -> list[str]:
        """품목표의 품목명 목록(시행규칙 품목명과 운용요령 표기). 조건 추출 모델이 조회어를 고를 때 쓴다."""
        evidence = self.evidence()
        return list(dict.fromkeys(name for item in evidence.items for name in (item.name, *item.scope_names)))

    def search(self, terms: list[str], *, top_k: int) -> ChildrenCandidates:
        evidence = self.evidence()
        items = rank_rows(
            evidence.items, terms, top_k=top_k, key=lambda item: item.item_id,
            text=lambda item: " ".join((item.name, *item.scope_names)),
            names=lambda item: [item.name, *item.scope_names],
        ) if terms else []
        return ChildrenCandidates(items=tuple(items), common_standard=evidence.common_standard,
                                  definitions=evidence.definitions, rule=evidence.rule, notice=evidence.notice,
                                  documents=evidence.documents())


def _load_on_demand(as_of: date) -> ChildrenEvidence:
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다."""
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return load_children_evidence(clients, as_of)
    finally:
        clients.close()


_default_lock = threading.Lock()
_default_search: LawApiItemSearch | None = None


def default_item_search() -> LawApiItemSearch:
    """조립 코드가 주입하지 않았을 때 쓰는 프로세스 공용 조회 경로."""
    global _default_search
    with _default_lock:
        if _default_search is None:
            _default_search = LawApiItemSearch(CachedLoader(_load_on_demand).load)
        return _default_search


class DatabaseItemSearch:
    """품목 행을 DB에서 조회하는 경로. 테이블이 없어 자리만 둔다.

    필요한 것(칸 정의: 클로드 md파일 "어린이·전파 품목표 칸 정의"):
    - 표 A 시행규칙 품목: 제도, 번호, 품목명, 적용 안전기준, 삭제 여부, 행 원문, 법령 버전
    - 표 B 운용요령 적용범위: 제도, 품목명(운용요령 표기), 연결 품목 행 ID, 하위 범위, 적용범위 원문,
      연령 조건 원문·숫자, 제외 조건 원문, 법령 버전
    - 법 제2조 제1호·제12호 원문, 시행규칙 별표 3의 2.(공통안전기준) 원문
    - 적재 작업: 법제처 조회 → 파싱 에이전트 → 검증 → 임베딩 → 저장
    구현하면 같은 ChildrenCandidates를 돌려주므로 ChildrenTool은 바꾸지 않는다.

    Args:
        session_factory: app.database.get_session_factory()가 돌려주는 세션 팩토리.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def catalog(self) -> list[str]:
        raise NotImplementedError("DB 품목 조회는 어린이제품 품목표 적재 후 구현합니다.")

    def search(self, terms: list[str], *, top_k: int) -> ChildrenCandidates:
        raise NotImplementedError("DB 품목 조회는 어린이제품 품목표 적재 후 구현합니다.")
