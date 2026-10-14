"""실제 상세페이지 구조에서 정제 결과가 바뀌지 않는지 검증한다.

가짜 페이지(conftest)는 구역 순서만 흉내 내서, 실제 페이지에서만 생기는 경우(표지가 여러 번 나옴,
제목 줄이 두 번 있음 등)를 놓친다. 실제 원문 28건에서 화면 표지 줄만 남긴 뼈대
(tests/fixtures/seller_region, scripts/make_seller_region_skeletons.py로 생성)로 결과를 고정한다.
표지를 바꾸거나 자르는 규칙을 고치면 여기서 실패한다.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from app.utils.seller_region import extract_seller_region

SKELETON_DIR = Path(__file__).parents[1] / "fixtures" / "seller_region"
TITLE = "판매자 상품 제목 자리표시 (Temu는 구역에서 가장 긴 줄을 제목으로 찾으므로 이 줄을 일부러 길게 둔다)"
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


def _skeleton_script():
    path = Path(__file__).parents[2] / "scripts" / "make_seller_region_skeletons.py"
    spec = importlib.util.spec_from_file_location("make_seller_region_skeletons", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_표지_목록에_있는_줄에서_잘리면_경계_문제가_없다(aliexpress_page):
    region = extract_seller_region(aliexpress_page)

    assert region.trimmed
    assert _skeleton_script().unknown_boundaries(aliexpress_page, region.text) == []


def test_표지_목록에_없는_줄에서_잘리면_경계_줄을_돌려준다(aliexpress_page):
    # 정제 코드에 "제품 설명" 표지를 추가하고 스크립트 목록에는 넣지 않은 경우를 흉내 낸다.
    region = extract_seller_region(aliexpress_page)
    lines = region.text.splitlines()
    cut = lines[: lines.index("제품 설명")]

    problems = _skeleton_script().unknown_boundaries(aliexpress_page, "\n".join(cut))

    assert problems == ["끝 경계 '제품 설명'"]
