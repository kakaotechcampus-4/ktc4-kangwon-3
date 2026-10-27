"""전파 대상기자재 조회. 조회는 "비슷한 기자재 고르기"이지 판단이 아니다.

- RadioItemSearch: Tool이 쓰는 조회 인터페이스.
- LawApiItemSearch: 지금 쓰는 경로. 법제처 응답을 직접 읽어 행을 만들고 기준일별로 캐시한다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from ..common.law import KST, CachedLoader, DocRef, LawApiClients
from ..common.ranking import rank_rows
from .evidence import Exemption, RadioEvidence, RadioItem, load_radio_evidence


@dataclass(frozen=True)
class RadioCandidates:
    """조회 결과. items는 상품과 비슷한 대상기자재 행(terms가 비면 빈 목록)."""

    items: tuple[RadioItem, ...]
    law: DocRef
    decree: DocRef
    notice: DocRef
    obligation: dict[str, str]
    personal_use: Exemption | None
    section_notes: dict[str, str] = field(default_factory=dict)
    documents: list[dict[str, str]] = field(default_factory=list)


class RadioItemSearch(Protocol):
    def catalog(self) -> list[str]:
        """대상기자재 분류명 목록.

        Returns:
            list[str]: 조건 추출 모델에 줄 분류명.
        """
        ...

    def search(self, terms: list[str], *, top_k: int) -> RadioCandidates:
        """상품 용어와 비슷한 대상기자재 행을 찾는다.

        Args:
            terms: 상품 용어.
            top_k: 돌려줄 최대 행 수.

        Returns:
            RadioCandidates: 후보 행과 근거 문서.
        """
        ...


class LawApiItemSearch:
    """법제처 API로 전파법·시행령·고시를 받아 대상기자재 행을 만든다. 기준일(한국 날짜)별로 캐시한다.

    Args:
        loader: 기준일을 받아 RadioEvidence를 돌려주는 함수(보통 CachedLoader.load).
        as_of: 고정 기준일. None이면 호출 시점의 한국 날짜.
    """

    def __init__(self, loader, *, as_of: date | None = None):
        self._loader = loader
        self._as_of = as_of

    def evidence(self) -> RadioEvidence:
        """기준일 근거를 읽는다.

        Returns:
            RadioEvidence: 기준일 근거 묶음.
        """
        return self._loader(self._as_of or datetime.now(KST).date())

    def catalog(self) -> list[str]:
        """대상기자재 분류명 목록(바깥 두 단계, 번호 제외). 조건 추출 모델이 조회어를 고를 때 쓴다.

        Returns:
            list[str]: 중복을 뺀 분류명.
        """
        return list(dict.fromkeys(" > ".join(item.plain_path[:2]) for item in self.evidence().items if item.path))

    def search(self, terms: list[str], *, top_k: int) -> RadioCandidates:
        """상품 용어와 비슷한 대상기자재 행을 찾는다.

        Args:
            terms: 상품 용어. 비면 후보 없이 근거만 돌려줌.
            top_k: 돌려줄 최대 행 수.

        Returns:
            RadioCandidates: 후보 행과 근거 문서.
        """
        evidence = self.evidence()
        items = rank_rows(
            evidence.items, terms, top_k=top_k, key=lambda item: item.item_id,
            text=lambda item: " ".join((*item.plain_path, item.remark)),
            names=lambda item: list(item.plain_path),
        ) if terms else []
        return RadioCandidates(
            items=tuple(items), law=evidence.law, decree=evidence.decree, notice=evidence.notice,
            obligation=evidence.obligation, personal_use=evidence.personal_use,
            section_notes=evidence.section_notes, documents=evidence.documents(),
        )


def _load_on_demand(as_of: date) -> RadioEvidence:
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다.

    Args:
        as_of: 기준일.

    Returns:
        RadioEvidence: 기준일 근거 묶음.
    """
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return load_radio_evidence(clients, as_of)
    finally:
        clients.close()


def law_api_item_search() -> LawApiItemSearch:
    """법제처 API 조회 경로를 만든다. 기준일별 캐시는 객체 안에 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        LawApiItemSearch: 조회할 때 법제처 클라이언트를 열고 닫는 조회 경로.
    """
    return LawApiItemSearch(CachedLoader(_load_on_demand).load)
