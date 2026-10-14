"""품목표 행을 상품 용어와의 글자 유사도로 고르는 단순 조회. DB 벡터 조회로 바꾸기 전까지 쓴다."""

import math
import re
from collections import Counter
from collections.abc import Callable, Iterable
from typing import TypeVar

from .law import compact

_T = TypeVar("_T")


def _bigrams(text: str) -> Counter:
    chars = re.sub(r"[^0-9A-Za-z가-힣]", "", text)
    return Counter(chars[i:i + 2] for i in range(len(chars) - 1)) if len(chars) > 1 else Counter([chars])


def rank_rows(rows: Iterable[_T], terms: list[str], *, text: Callable[[_T], str],
              names: Callable[[_T], list[str]], key: Callable[[_T], str], top_k: int) -> list[_T]:
    """행 이름과 상품 용어의 글자 2개 단위 유사도로 정렬한다.

    용어마다 따로 유사도를 재서 가장 높은 값을 쓴다(상품명·제품 종류·조회어를 이어 붙이면 서로 희석된다).
    모든 행에 나오는 글자는 가중치를 낮추고(IDF), 행 이름이 상품 용어에 그대로 들어 있으면 가산한다.
    상품 용어별 동의어 사전은 두지 않는다. 상품명을 품목표 명칭으로 바꾸는 일은 조건 추출 모델의 조회어가 맡는다.

    Args:
        rows: 후보 행.
        terms: 상품 용어(조회어·제품 종류·상품명 등).
        text: 행에서 유사도를 잴 글.
        names: 행 이름 목록(포함 가산용).
        key: 같은 점수일 때 순서를 정할 행 ID.
        top_k: 돌려줄 최대 행 수. 점수가 0인 행은 빼는다.
    """
    rows = list(rows)
    documents = [_bigrams(text(row)) for row in rows]
    frequency = Counter(gram for document in documents for gram in document)
    idf = {gram: math.log((1 + len(rows)) / (1 + count)) + 1 for gram, count in frequency.items()}
    queries = list(dict.fromkeys(term.strip() for term in terms if term and term.strip()))
    query_compact = [compact(term) for term in queries]

    def weight(vector: Counter) -> dict[str, float]:
        return {gram: count * idf.get(gram, 0.0) for gram, count in vector.items()}

    def norm(weights: dict[str, float]) -> float:
        return math.sqrt(sum(value * value for value in weights.values())) or 1.0

    query_weights = [weight(_bigrams(term)) for term in queries]
    scored = []
    for row, document in zip(rows, documents):
        weights = weight(document)
        row_norm = norm(weights)
        score = max((sum(q[gram] * weights.get(gram, 0.0) for gram in q) / (norm(q) * row_norm)
                     for q in query_weights), default=0.0)
        row_names = [compact(name) for name in names(row)]
        if any(len(name) > 1 and any(len(term) > 1 and (name in term or term in name) for term in query_compact)
               for name in row_names):
            score += 1.0
        scored.append((score, key(row), row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [row for score, _, row in scored[:top_k] if score > 0]
