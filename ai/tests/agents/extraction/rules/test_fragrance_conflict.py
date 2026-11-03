"""rules.py 향 모순 후보: 제목은 향 제품인데 상품 정보에 향 없음 표기가 있으면 검토 후보로 보고 (#532)."""

import pytest

from app.agents.extraction.rules import detect_fragrance_conflict


@pytest.mark.parametrize("title, spec, claim, shown", [
    ("장식용 꽃 향기 디퓨저 스틱", "향: 무향", "향기", "향: 무향"),
    ("차량용 에어벤트 클립 방향제", "향기: Fragrance-Free", "방향제", "Fragrance-Free"),
    ("Car Aroma Diffuser Clip", "Scent: Unscented", "Aroma", "Unscented"),
    ("차량용 방향제", "향이 있든 없든: \n아니요", "방향제", "향이 있든 없든: 아니요"),
])
def test_향_제품_제목과_향_없음_표기가_같이_있으면_모순_후보로_잡는다(title, spec, claim, shown):
    conflicts = detect_fragrance_conflict([title], [f"{title}\n{spec}"])

    assert len(conflicts) == 1
    assert f"'{claim}'" in conflicts[0]
    assert f"'{shown}'" in conflicts[0]


def test_향_없음_표기만_있으면_모순이_아니다():
    # 무향 세제·무향 로션처럼 향 제품이 아닌 상품
    assert detect_fragrance_conflict(["저자극 세탁 세제 2L"], ["향: 무향"]) == []


def test_향_제품이고_향_없음_표기가_없으면_모순이_아니다():
    assert detect_fragrance_conflict(["라벤더 향기 디퓨저"], ["용량: 100ml", "향: 라벤더"]) == []


def test_제목의_Fragrance_Free는_향_제품_표현으로_보지_않는다():
    assert detect_fragrance_conflict(["Fragrance-Free Baby Lotion"], ["Unscented"]) == []


def test_설명_속_향기는_제목이_아니라서_보지_않는다():
    # 제목만 본다. 설명에 "향기"가 있어도 제목이 향 제품이 아니면 모순 후보가 아니다
    assert detect_fragrance_conflict(["원목 수납함"], ["은은한 나무 향기", "향: 무향 처리"]) == []


def test_제목을_못_찾으면_첫_블록의_첫_줄을_제목으로_본다():
    conflicts = detect_fragrance_conflict([], ["\n아로마 디퓨저 스틱 세트\n구성: 스틱 10개", "향: 무향"])

    assert len(conflicts) == 1
