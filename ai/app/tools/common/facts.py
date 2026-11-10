"""상품 원문 인용 조각 만들기와 모델이 뽑은 조건의 원문 대조."""

import re
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
    값은 낱말 사이에 다른 낱말이 끼어도 된다. 다만 숫자가 든 낱말과 부정 표현은 건너뛸 수 없다 (_words_in_order).
    인용은 원문에 이어서 있어야 하므로 지어낸 값은 그대로 막힌다.

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
    return not value_in_quote or _words_in_order(fact.value, fact.quote)


def _normalize(text: str | None) -> str:
    """원문 대조용 글. 전각·호환 문자를 보통 글자로 맞추고(NFKC) 공백·표 테두리를 지우고 대소문자를 없앤다.

    Args:
        text: 원문. None이면 빈 글로 봄.

    Returns:
        str: 대조용 글.
    """
    return compact(unicodedata.normalize("NFKC", text or "")).casefold()


def _words_in_order(value: str, quote: str) -> bool:
    """값이 인용 안에 있는지. 이어서 있거나, 낱말 단위로 순서대로 있되 건너뛴 낱말에 수치·부정이 없으면 True.

    모델이 가운데 낱말을 빼고 적은 값(인용 "탁상용 미니 선풍기" → 값 "탁상용 선풍기")은 받고, 건너뛰면 뜻이
    바뀌는 낱말을 넘어 만든 값은 막는다 (#749 리뷰):
    - 숫자가 든 낱말: 인용 "Input: 5V 1A, Output: 12V 2A" → 값 "5V 2A"는 원문에 없는 수치 조합
    - 부정 표현: 인용 "어린이용 아님, 성인용 탁상 선풍기" → 값 "어린이용 선풍기"
    낱말은 통째로 같아야 맞는 것으로 본다 ("포함"이 "미포함" 안에서 찾아지지 않게).

    Args:
        value: 모델이 적은 값.
        quote: 모델이 적은 인용 (원문 그대로).

    Returns:
        bool: 값이 인용에 맞으면 True. 빈 값은 False.
    """
    joined = _normalize(value)
    if not joined:
        return False
    if joined in _normalize(quote):
        return True
    words, quote_words = _words(value), _words(quote)
    if not words:
        return False
    # 값의 첫 낱말은 인용 어디서든 시작할 수 있음. 그 뒤로는 건너뛸 수 없는 낱말을 넘지 않고 이어져야 함
    return any(_follows(words[1:], quote_words, start + 1)
               for start, word in enumerate(quote_words) if word == words[0])


# 값의 낱말 사이에서 건너뛰면 뜻이 뒤집히는 부정 표현. 손으로 정한 목록이라 빠진 표현이 있을 수 있음.
# 한국어는 낱말에 붙어 나오므로 포함 여부로, 영어는 낱말 전체로 본다.
_NEGATION_PARTS = ("아님", "아닌", "아니", "없음", "없는", "없이", "않", "미포함", "불포함", "비포함", "제외", "미지원",
                   "불가", "불필요")
_NEGATION_WORDS = frozenset({"not", "no", "non", "without", "excluded", "excluding"})
# 낱말 경계: 공백과 문장부호. 마침표는 숫자 사이(예: 5.8GHz)가 아니면 경계로 본다
_WORD_SPLIT = re.compile(r"[\s,|:;/()\[\]{}<>\"'!?·~]+|(?<!\d)\.|\.(?!\d)")


def _words(text: str) -> list[str]:
    """대조용 낱말 목록. 정규화(NFKC·대소문자)한 뒤 공백·문장부호로 나누고 앞뒤 하이픈을 뗀다.

    Args:
        text: 원문.

    Returns:
        list[str]: 빈 낱말을 뺀 낱말 목록.
    """
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return [word for word in (part.strip("-") for part in _WORD_SPLIT.split(normalized)) if word]


def _skippable(word: str) -> bool:
    """값의 낱말 사이에서 건너뛰어도 되는 인용 낱말인지. 숫자가 들었거나 부정 표현이면 False.

    Args:
        word: 인용 낱말 (정규화됨).

    Returns:
        bool: 건너뛰어도 되면 True.
    """
    if any(char.isdigit() for char in word):
        return False
    return word not in _NEGATION_WORDS and not any(part in word for part in _NEGATION_PARTS)


def _follows(words: list[str], quote_words: list[str], start: int) -> bool:
    """남은 값 낱말이 인용의 start부터 순서대로 나오는지. 사이에 낀 인용 낱말은 건너뛸 수 있는 것만 넘는다.

    Args:
        words: 아직 찾지 않은 값 낱말.
        quote_words: 인용 낱말.
        start: 찾기 시작할 인용 위치.

    Returns:
        bool: 모두 찾으면 True.
    """
    position = start
    for word in words:
        while position < len(quote_words) and quote_words[position] != word:
            if not _skippable(quote_words[position]):
                return False
            position += 1
        if position == len(quote_words):
            return False
        position += 1
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
