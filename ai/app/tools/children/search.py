"""어린이제품 품목 조회. 조회는 "비슷한 품목 고르기"이지 판단이 아니다.

- ChildrenItemSearch: Tool이 쓰는 조회 인터페이스.
- LawApiItemSearch: 지금 쓰는 경로. 법제처 응답을 직접 읽어 품목 행을 만들고 기준일별로 캐시한다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from ..common.law import KST, CachedLoader, DocRef, LawApiClients
from ..common.ranking import rank_rows
from .evidence import ChildrenEvidence, ChildrenItem, Definitions, Scheme, load_children_evidence, without_includes


@dataclass(frozen=True)
class ChildrenCandidates:
    """조회 결과. items는 상품과 비슷한 품목 행(terms가 비면 빈 목록).

    designated는 안전인증·안전확인 품목 전체다. 맞는 품목이 없을 때 공급자적합성확인으로 낮춰 안내하므로,
    그 판단 전에 품목 선택 모델이 두 제도의 품목을 빠짐없이 보게 한다(조회 순위에서 빠져도 낮춰지지 않게).
    """

    items: tuple[ChildrenItem, ...]
    common_standard: ChildrenItem
    definitions: Definitions
    rule: DocRef
    notice: DocRef
    documents: list[dict[str, str]] = field(default_factory=list)
    designated: tuple[ChildrenItem, ...] = ()


class ChildrenItemSearch(Protocol):
    def catalog(self) -> list[str]:
        """품목명 목록.

        Returns:
            list[str]: 조건 추출 모델에 줄 품목명.
        """
        ...

    def search(self, terms: list[str], *, top_k: int) -> ChildrenCandidates:
        """상품 용어와 비슷한 품목 행을 찾는다.

        Args:
            terms: 상품 용어.
            top_k: 돌려줄 최대 행 수.

        Returns:
            ChildrenCandidates: 후보 행과 근거 문서.
        """
        ...


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
        """기준일 근거를 읽는다.

        Returns:
            ChildrenEvidence: 기준일 근거 묶음.
        """
        return self._loader(self._as_of or datetime.now(KST).date())

    def catalog(self) -> list[str]:
        """품목표의 품목명 목록(시행규칙 품목명과 운용요령 표기). 조건 추출 모델이 조회어를 고를 때 쓴다.

        Returns:
            list[str]: 포함 문구를 뗀 품목명 (중복 제거).
        """
        evidence = self.evidence()
        return list(dict.fromkeys(without_includes(name) for item in evidence.items
                                  for name in (item.name, *item.scope_names)))

    def search(self, terms: list[str], *, top_k: int) -> ChildrenCandidates:
        """상품 용어와 비슷한 품목 행을 찾는다.

        Args:
            terms: 상품 용어. 비면 후보 없이 근거만 돌려줌.
            top_k: 돌려줄 최대 행 수.

        Returns:
            ChildrenCandidates: 후보 행과 근거 문서.
        """
        evidence = self.evidence()
        # 순위에는 포함 문구를 뗀 이름만 쓴다("포함한다" 같은 글자가 유사도에 섞이지 않게).
        items = rank_rows(
            evidence.items, terms, top_k=top_k, key=lambda item: item.item_id,
            text=lambda item: " ".join(without_includes(name) for name in (item.name, *item.scope_names)),
            names=lambda item: [without_includes(name) for name in (item.name, *item.scope_names)],
        ) if terms else []
        designated = tuple(item for item in evidence.items if item.scheme in (Scheme.CERTIFICATION, Scheme.CONFIRMATION))
        return ChildrenCandidates(items=tuple(items), designated=designated, common_standard=evidence.common_standard,
                                  definitions=evidence.definitions, rule=evidence.rule, notice=evidence.notice,
                                  documents=evidence.documents())


def _load_on_demand(as_of: date) -> ChildrenEvidence:
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다.

    Args:
        as_of: 기준일.

    Returns:
        ChildrenEvidence: 기준일 근거 묶음.
    """
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return load_children_evidence(clients, as_of)
    finally:
        clients.close()


def law_api_item_search() -> LawApiItemSearch:
    """법제처 API 조회 경로를 만든다. 기준일별 캐시는 객체 안에 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        LawApiItemSearch: 조회할 때 법제처 클라이언트를 열고 닫는 조회 경로.
    """
    return LawApiItemSearch(CachedLoader(_load_on_demand).load)
