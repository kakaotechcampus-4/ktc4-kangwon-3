"""규제 Tool 실행 한 번의 상태. 훅과 공통 부품이 이 객체 하나를 주고받음."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ...schemas.agent import ToolSelectionItem
from ...schemas.product import Product


def _initial_query() -> dict[str, Any]:
    """결과 query의 기본 카운터. 5개 Tool이 모두 남기는 값."""
    return {"dropped_facts": 0, "dropped_candidates": 0, "not_applicable": 0}


@dataclass
class ToolRun:
    """Tool 실행 한 번의 상태. 실행마다 새로 만들고 Tool 인스턴스에는 두지 않음 (동시 실행 대비).

    Attributes:
        product: 검토할 상품.
        decision: 이 Tool의 선택 결정.
        snippets: 인용 근거가 되는 상품 원문 조각 (조각 ID → 원문).
        extracted: 조건 추출 단계의 모델 출력. 추출 전이면 None.
        facts: 원문과 대조된 조건.
        by_field: facts를 필드별로 묶은 것.
        missing: 재질문할 필드 (중복은 결과 조립 때 제거).
        conflicted: 값이 서로 달라 판단하지 않은 필드.
        assumptions: 결과에 남길 가정.
        actions: 판매 전 할 일 (중복은 결과 조립 때 제거).
        query: 조회·선택 기록 (버린 수, 후보 ID 등). 흔들림 측정과 운영 디버깅용.
    """

    product: Product
    decision: ToolSelectionItem
    snippets: dict[str, str] = field(default_factory=dict)
    extracted: BaseModel | None = None
    facts: list[Any] = field(default_factory=list)
    by_field: dict[str, list[Any]] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    query: dict[str, Any] = field(default_factory=_initial_query)
