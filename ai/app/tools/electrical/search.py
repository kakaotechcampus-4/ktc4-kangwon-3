"""상품 조건으로 전기용품 품목표의 후보 행을 찾는다.

법령 원문 전체를 모델에 넣지 않고, 운용요령 별표 1~3의 품목 행(AnnexBlock) 중 상품과 비슷한
몇 개만 고른다. 조회는 "비슷한 물건 고르기"이지 판단이 아니다. 정답 품목이 후보에 없을 수 있으므로
후보가 비거나 맞는 행이 없으면 Tool은 정보 부족으로 처리하고 비대상으로 바꾸지 않는다.

조회 경로는 ElectricalItemSearch로 추상화한다.
- LawApiItemSearch: 법제처 API로 받은 품목표를 메모리에서 찾는다(현재 사용, DB 적재 전 임시 경로).
- DatabaseItemSearch: 품목표 행 테이블·임베딩 적재 후 벡터 조회로 바꿀 자리(스텁).
"""

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from ..common.law import CachedLoader
from ..common.ranking import rank_rows
from .evidence import (
    AnnexBlock,
    ElectricalEvidence,
    ElectricalEvidenceSource,
    EvidenceSection,
    LawApiClients,
    LawApiEvidenceSource,
    Scheme,
)

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class ItemCandidates:
    """조회 결과. 후보 행과, 판단에 늘 함께 쓰는 범위 조문·표 공통 비고·구매대행 특례 목록."""

    blocks: tuple[AnnexBlock, ...]
    rule_scope: EvidenceSection
    notice_scope: EvidenceSection
    documents: list[dict[str, str]]
    # 운용요령 별표 1~3 끝의 공통 비고(전지 전용 구조·차량 전용구조 제외 등). 제도별.
    common_notes: dict[Scheme, EvidenceSection] = field(default_factory=dict)
    # 시행규칙 별표 13(구매대행의 특례 제품) 전기용품 부분. 제도별. 확인하지 못하면 비어 있다.
    purchase_agent: dict[Scheme, EvidenceSection] = field(default_factory=dict)


class ElectricalItemSearch(Protocol):
    """상품 용어로 품목표 후보 행을 찾는다. 판단하지 않는다."""

    def search(self, terms: list[str], *, top_k: int) -> ItemCandidates: ...


def rank_blocks(blocks, terms: list[str], *, top_k: int) -> list[AnnexBlock]:
    """품목·세부품목 이름과 상품 용어의 글자 2개 단위 유사도로 정렬한다(공용 rank_rows).

    세부품목 이름이 상품 용어에 그대로 들어 있으면 가산한다(세부품목이 없는 행은 품목 이름).
    상품 용어별 동의어 사전은 두지 않는다. 제품 종류를 보통 명칭으로 바꾸는 일은 조건 추출 LLM의
    search_terms가 맡는다. 정답 품목이 상위에 드는지(recall)는 평가셋으로 따로 잰다.
    """
    return rank_rows(
        blocks, terms, top_k=top_k, key=lambda block: block.block_id,
        text=lambda block: " ".join((*block.items, *block.sub_items)),
        names=lambda block: list(block.sub_items) or list(block.items),
    )


class LawApiItemSearch:
    """법제처 API로 받은 품목표에서 찾는다. 근거는 기준일별로 캐시해 상품마다 다시 받지 않는다.

    Args:
        source: 근거 조회 경로(load(기준일)을 가진 객체). 보통 CachedLoader(LawApiEvidenceSource(client).load).
        as_of: 기준일. 없으면 실행 시점의 한국 날짜.
    """

    def __init__(self, source: ElectricalEvidenceSource, *, as_of: date | None = None):
        self._source = source
        self._as_of = as_of

    def load(self) -> ElectricalEvidence:
        return self._source.load(self._as_of or datetime.now(KST).date())

    def search(self, terms: list[str], *, top_k: int) -> ItemCandidates:
        evidence = self.load()
        sections = (evidence.rule_scope, evidence.notice_scope)
        return ItemCandidates(
            blocks=tuple(rank_blocks(evidence.blocks, terms, top_k=top_k)),
            rule_scope=evidence.rule_scope, notice_scope=evidence.notice_scope,
            documents=[{"id": s.document_id, "version": s.version_id, "effective_date": s.effective_date}
                       for s in sections],
            common_notes=dict(evidence.common_notes),
            purchase_agent=dict(evidence.purchase_agent),
        )


def _load_on_demand(as_of: date) -> ElectricalEvidence:
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다."""
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return LawApiEvidenceSource(clients).load(as_of)
    finally:
        clients.close()


_default_lock = threading.Lock()
_default_search: LawApiItemSearch | None = None


def default_item_search() -> LawApiItemSearch:
    """조립 코드가 주입하지 않았을 때 쓰는 프로세스 공용 조회 경로."""
    global _default_search
    with _default_lock:
        if _default_search is None:
            _default_search = LawApiItemSearch(CachedLoader(_load_on_demand))
        return _default_search


class DatabaseItemSearch:
    """품목표 행을 DB 벡터 조회로 찾는 경로. 테이블이 없어 자리만 둔다.

    필요한 것(현재 DB에는 조문 테이블 law_articles만 있다):
    - 행정규칙(운용요령) 문서·버전 테이블
    - 품목표 행 테이블: 문서 버전 FK, 제도, 분류, 품목, 세부품목, 비고, 저전압 포함 여부, 행 원문, 임베딩
    - 적재 작업: 법제처 조회 → parse_annex → 임베딩(app.utils.embedding.embed_texts) → 저장
    구현하면 같은 ItemCandidates를 돌려주므로 ElectricalTool은 바꾸지 않는다.

    Args:
        session_factory: app.database.get_session_factory()가 돌려주는 세션 팩토리.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def search(self, terms: list[str], *, top_k: int) -> ItemCandidates:
        # TODO: 품목표 행 테이블과 적재 작업이 생기면 embed_text(" ".join(terms))로 벡터 조회한다.
        raise NotImplementedError("DB 품목 조회는 품목표 행 테이블 적재 후 구현합니다.")
