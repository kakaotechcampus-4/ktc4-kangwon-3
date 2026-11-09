"""상품 원문 인용 조각 만들기와 모델이 뽑은 조건의 원문 대조."""

import unicodedata
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
    """인용이 지정한 원문 조각 안에 있는지, 값의 낱말이 인용 안에 순서대로 있는지.

    대조는 공백·대소문자·전각 문자 차이를 무시한다. 모델이 값을 다듬어 적는 경우를 받기 위해
    (재현: 인용 "탁상용 미니 선풍기"에 값 "탁상용 선풍기", 인용 "Desk Fan"에 값 "Desk fan")
    값은 낱말 사이에 다른 글자가 끼어도 된다. 인용은 원문에 이어서 있어야 하므로 지어낸 값은 그대로 막힌다.

    Args:
        fact: 모델이 뽑은 조건 (조각 ID·인용·값).
        snippets: 상품 원문 조각 (조각 ID → 원문).
        value_in_quote: False면 값은 판단 결과(예: "예"/"아니오")라 인용 안에 없어도 된다.

    Returns:
        bool: 인용이 지정한 조각에 있고 (value_in_quote면) 값의 낱말도 인용 안에 순서대로 있으면 True.
    """
    source = snippets.get(fact.evidence_id)
    quote = _normalize(fact.quote)
    if source is None or not quote or quote not in _normalize(source):
        return False
    return not value_in_quote or _words_in_order(fact.value, quote)


def _normalize(text: str | None) -> str:
    """원문 대조용 글. 전각·호환 문자를 보통 글자로 맞추고(NFKC) 공백·표 테두리를 지우고 대소문자를 없앤다.

    Args:
        text: 원문. None이면 빈 글로 봄.

    Returns:
        str: 대조용 글.
    """
    return compact(unicodedata.normalize("NFKC", text or "")).casefold()


def _words_in_order(value: str, quote: str) -> bool:
    """값을 공백으로 나눈 낱말이 모두 인용 안에 순서대로 있는지. 빈 값은 False.

    Args:
        value: 모델이 적은 값.
        quote: 대조용으로 정리한 인용.

    Returns:
        bool: 낱말이 모두 앞에서부터 차례로 찾아지면 True.
    """
    words = [word for word in (_normalize(part) for part in (value or "").split()) if word]
    if not words:
        return False
    position = 0
    for word in words:
        found = quote.find(word, position)
        if found < 0:
            return False
        position = found + len(word)
    return True


# 인용 문구 끝에 붙는 문장부호. 조사는 그 앞 글자의 받침으로 정한다 (리뷰 #643: "'습기 차단.'를").
_TRAILING_PUNCTUATION = " \t.,!?;:)]}'\"”’…·~"


def object_particle(word: str) -> str:
    """목적격 조사. 마지막 글자에 받침이 있으면 "을", 없으면 "를".

    Args:
        word: 조사를 붙일 낱말.

    Returns:
        str: "을" 또는 "를". 마지막 글자가 한글이 아니면 "를".
    """
    return "을" if _ends_with_final_consonant(word) else "를"


def topic_particle(word: str) -> str:
    """보조사 은·는. 마지막 글자에 받침이 있으면 "은", 없으면 "는".

    Args:
        word: 조사를 붙일 낱말.

    Returns:
        str: "은" 또는 "는". 마지막 글자가 한글이 아니면 "는".
    """
    return "은" if _ends_with_final_consonant(word) else "는"


def _ends_with_final_consonant(word: str) -> bool:
    """마지막 글자가 받침 있는 한글인지. 한글이 아니면 False. 끝의 문장부호·공백은 빼고 본다."""
    last = word.rstrip(_TRAILING_PUNCTUATION)[-1:]
    return "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0


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
