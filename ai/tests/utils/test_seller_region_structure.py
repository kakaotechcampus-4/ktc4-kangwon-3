"""실제 상세페이지 구조에서 정제 결과가 바뀌지 않는지 검증한다.

가짜 페이지(conftest)는 구역 순서만 흉내 내서, 실제 페이지에서만 생기는 경우(표지가 여러 번 나옴,
제목 줄이 두 번 있음 등)를 놓친다. 실제 원문 28건에서 화면 표지 줄만 남긴 뼈대
(tests/fixtures/seller_region, scripts/make_seller_region_skeletons.py로 생성)로 결과를 고정한다.
표지를 바꾸거나 자르는 규칙을 고치면 여기서 실패한다.
"""

import json
from pathlib import Path

import pytest

from app.utils.seller_region import extract_seller_region

SKELETON_DIR = Path(__file__).parents[1] / "fixtures" / "seller_region"
TITLE = "판매자 상품 제목 자리표시 " + "가" * 80
EXPECTED = json.loads((SKELETON_DIR / "expected.json").read_text(encoding="utf-8"))


def test_뼈대_픽스처가_원문_수만큼_있다():
    assert len(EXPECTED) >= 27
    assert {path.stem for path in SKELETON_DIR.glob("*.txt")} == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED), ids=str)
def test_실제_페이지_구조에서_정제_결과가_그대로다(name: str):
    expected = EXPECTED[name]

    region = extract_seller_region((SKELETON_DIR / f"{name}.txt").read_text(encoding="utf-8"))

    assert region.site == expected["site"]
    assert region.trimmed is expected["trimmed"]
    assert (region.title == TITLE) is expected["title"]
    assert region.text.splitlines() == expected["kept"]
