"""상품 원문 인용 조각 만들기와 모델이 뽑은 조건의 원문 대조."""

from typing import Protocol

from ...schemas.product import Product
from .law import compact


class QuotedFact(Protocol):
    field: str
    value: str
    evidence_id: str
    quote: str


def product_snippets(product: Product) -> dict[str, str]:
    """상품 인용 근거가 되는 조각. 판매 글(listing_text)과 속성의 원문(source_text)만 쓴다."""
    snippets = {f"listing-{i}": text for i, text in enumerate(product.listing_text) if text.strip()}
    snippets.update({f"attribute-{i}": attr.source_text for i, attr in enumerate(product.attributes)
                     if attr.source_text and attr.source_text.strip()})
    return snippets


def quote_matches(fact: QuotedFact, snippets: dict[str, str], *, value_in_quote: bool = True) -> bool:
    """인용이 지정한 원문 조각 안에 그대로 있는지, 값이 인용 안에 있는지.

    Args:
        value_in_quote: False면 값은 판단 결과(예: "예"/"아니오")라 인용 안에 없어도 된다.
    """
    source = snippets.get(fact.evidence_id)
    quote = compact(fact.quote)
    if source is None or not quote or quote not in compact(source):
        return False
    return not value_in_quote or (bool(compact(fact.value)) and compact(fact.value) in quote)


def group_facts(facts: list) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for fact in facts:
        grouped.setdefault(fact.field, []).append(fact)
    return grouped
