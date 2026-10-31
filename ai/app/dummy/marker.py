"""더미 케이스 선택. 접수 때 고른 케이스를 입력 text_blocks에 표시로 남겨 재진단까지 이어 씀."""

import random
import re

from ..schemas.agent import ExtractionInput
from .cases import DummyCaseName

_MARKER_RE = re.compile(r"^\[dummy:case=(\w+)\]$")


def random_case(rng: random.Random | None = None) -> DummyCaseName:
    """케이스를 무작위로 고른다. 실패 케이스 포함.

    Args:
        rng: 난수 생성기. 테스트 고정용. 없으면 새로 만듦.

    Returns:
        DummyCaseName: 고른 케이스.
    """
    return (rng or random.Random()).choice(list(DummyCaseName))


def mark_case(item: ExtractionInput, case: DummyCaseName) -> ExtractionInput:
    """케이스 표시를 text_blocks 끝에 붙인 입력을 만든다.

    Args:
        item: 상품 입력.
        case: 남길 케이스.

    Returns:
        ExtractionInput: 표시가 붙은 새 입력.
    """
    return item.model_copy(update={"text_blocks": [*item.text_blocks, f"[dummy:case={case}]"]})


def read_case(item: ExtractionInput) -> DummyCaseName:
    """입력에 남긴 케이스 표시를 읽는다.

    Args:
        item: mark_case로 표시를 붙인 상품 입력.

    Returns:
        DummyCaseName: 표시된 케이스.

    Raises:
        ValueError: 표시가 없거나 값이 잘못된 경우.
    """
    for block in reversed(item.text_blocks):
        if match := _MARKER_RE.match(block):
            return DummyCaseName(match[1])
    raise ValueError(f"더미 케이스 표시가 없습니다: {item.product_id}")
