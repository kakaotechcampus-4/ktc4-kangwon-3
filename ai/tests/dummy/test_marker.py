"""더미 케이스 표시를 입력에 남기고 다시 읽는지, 무작위 선택이 모든 케이스를 내는지 확인한다."""

import random

import pytest

from app.dummy import DummyCaseName, mark_case, random_case, read_case
from app.schemas.agent import ExtractionInput

_ITEM = ExtractionInput(product_id="p-1", text_blocks=["상품 설명"])


@pytest.mark.parametrize("case", list(DummyCaseName))
def test_남긴_케이스를_그대로_읽는다(case):
    marked = mark_case(_ITEM, case)

    assert read_case(marked) is case
    assert marked.text_blocks[0] == "상품 설명"
    assert _ITEM.text_blocks == ["상품 설명"]


@pytest.mark.parametrize("blocks", [["상품 설명"], ["[dummy:case=unknown]"]])
def test_표시가_없거나_값이_잘못되면_거절한다(blocks):
    with pytest.raises(ValueError):
        read_case(ExtractionInput(product_id="p-1", text_blocks=blocks))


def test_무작위_선택은_모든_케이스를_낸다():
    rng = random.Random(0)

    assert {random_case(rng) for _ in range(300)} == set(DummyCaseName)
