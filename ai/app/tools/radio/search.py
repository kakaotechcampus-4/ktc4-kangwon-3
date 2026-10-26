"""전파 대상기자재 조회. 조회는 "비슷한 기자재 고르기"이지 판단이 아니다.

- RadioItemSearch: Tool이 쓰는 조회 인터페이스.
- LawApiItemSearch: 지금 쓰는 경로. 법제처 응답을 직접 읽어 행을 만들고 기준일별로 캐시한다.
- DatabaseItemSearch: 적재 단계 파싱 에이전트가 고시 별표 1을 DB에 넣으면 쓸 경로(스텁).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from ..common.law import CachedLoader, DocRef, LawApiClients
from ..common.ranking import rank_rows
from .evidence import Exemption, RadioEvidence, RadioItem, load_radio_evidence

KST = timezone(timedelta(hours=9))


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
    def catalog(self) -> list[str]: ...
    def search(self, terms: list[str], *, top_k: int) -> RadioCandidates: ...


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
        return self._loader(self._as_of or datetime.now(KST).date())

    def catalog(self) -> list[str]:
        """대상기자재 분류명 목록(바깥 두 단계, 번호 제외). 조건 추출 모델이 조회어를 고를 때 쓴다."""
        return list(dict.fromkeys(" > ".join(item.plain_path[:2]) for item in self.evidence().items if item.path))

    def search(self, terms: list[str], *, top_k: int) -> RadioCandidates:
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


class DatabaseItemSearch:
    """대상기자재 행을 DB에서 조회하는 경로. 테이블이 없어 자리만 둔다.

    필요한 것(칸 정의: "어린이·전파 품목표 칸 정의"):
    - 표 C 고시 별표 1 행: 절, 분류 경로, 기자재명, 주파수 대역(원문·MHz), 적용분야, 평가유형, 기기부호,
      기타사항, 무선 행 여부, 행 원문, 법령 버전. 절별 비고
    - 표 D 시행령 별표 6의2 면제: 구분, 목, 면제대상 원문, 면제 수량, 면제 내용
    - 전파법 제58조의2 제1항~제4항 원문
    구현하면 같은 RadioCandidates를 돌려주므로 RadioTool은 바꾸지 않는다.

    Args:
        session_factory: app.database.get_session_factory()가 돌려주는 세션 팩토리.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def catalog(self) -> list[str]:
        raise NotImplementedError("DB 조회는 전파 대상기자재 적재 후 구현합니다.")

    def search(self, terms: list[str], *, top_k: int) -> RadioCandidates:
        raise NotImplementedError("DB 조회는 전파 대상기자재 적재 후 구현합니다.")
