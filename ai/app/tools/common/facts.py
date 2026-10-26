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
    """상품 인용 근거가 되는 조각. 판매 글(listing_text)과 속성의 원문(source_text)만 쓴다.

    Args:
        product: 검토할 상품.

    Returns:
        dict[str, str]: 조각 ID("listing-0", "attribute-0" 등) → 원문. 빈 글은 뺌.
    """
    snippets = {f"listing-{i}": text for i, text in enumerate(product.listing_text) if text.strip()}
    snippets.update({f"attribute-{i}": attr.source_text for i, attr in enumerate(product.attributes)
                     if attr.source_text and attr.source_text.strip()})
    return snippets


def quote_matches(fact: QuotedFact, snippets: dict[str, str], *, value_in_quote: bool = True) -> bool:
    """인용이 지정한 원문 조각 안에 그대로 있는지, 값이 인용 안에 있는지.

    Args:
        fact: 모델이 뽑은 조건 (조각 ID·인용·값).
        snippets: 상품 원문 조각 (조각 ID → 원문).
        value_in_quote: False면 값은 판단 결과(예: "예"/"아니오")라 인용 안에 없어도 된다.

    Returns:
        bool: 인용이 원문에 있고 (value_in_quote면) 값도 인용 안에 있으면 True.
    """
    source = snippets.get(fact.evidence_id)
    quote = compact(fact.quote)
    if source is None or not quote or quote not in compact(source):
        return False
    return not value_in_quote or (bool(compact(fact.value)) and compact(fact.value) in quote)


def object_particle(word: str) -> str:
    """목적격 조사. 마지막 글자에 받침이 있으면 "을", 없으면 "를".

    Args:
        word: 조사를 붙일 낱말.

    Returns:
        str: "을" 또는 "를". 마지막 글자가 한글이 아니면 "를".
    """
    last = word.rstrip()[-1:]
    if not ("가" <= last <= "힣"):
        return "를"
    return "을" if (ord(last) - ord("가")) % 28 else "를"


def group_facts(facts: list) -> dict[str, list]:
    """조건을 필드별로 묶는다.

    Args:
        facts: field 속성이 있는 조건 목록.

    Returns:
        dict[str, list]: 필드 → 그 필드의 조건 (들어온 순서 유지).
    """
    grouped: dict[str, list] = {}
    for fact in facts:
        grouped.setdefault(fact.field, []).append(fact)
    return grouped
