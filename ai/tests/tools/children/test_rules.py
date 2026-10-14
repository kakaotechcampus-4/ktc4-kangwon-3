"""어린이제품 연령 규칙(법 제2조 제1호 "만 13세 이하")을 확인한다."""

import pytest

from app.tools.children.rules import (
    AgeRange, age_value_bounded, child_state, combined_child_state, parse_age, sale_action,
)
from app.tools.children.evidence import Scheme


@pytest.mark.parametrize("text,expected", [
    ("만 3세 이상", AgeRange(36, None)),
    ("36개월 미만", AgeRange(None, 35)),
    ("3~7세", AgeRange(36, 95)),
    ("6개월~3세", AgeRange(6, 47)),
    ("만 13세 이하", AgeRange(None, 167)),
    ("14세 이상", AgeRange(168, None)),
    ("13세 초과", AgeRange(168, None)),
    ("8+", AgeRange(96, None)),
    ("5세", AgeRange(60, 71)),
    ("3세부터 사용", AgeRange(36, None)),
    ("만 14세 미만 사용 금지", AgeRange(168, None)),
    ("36개월 미만 어린이는 사용 금지", AgeRange(36, None)),
    ("3세 이하 사용 불가", None),
    ("3세트", None),
    ("100+", None),
])
def test_연령_표기를_개월_범위로_읽는다(text, expected):
    assert parse_age(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("만 3세 이상", True),
    ("36개월 미만", True),
    ("만 13세 이하", True),
    ("13세 이상", True),
    ("14세 이상", False),
    ("성인용", False),
    ("유아용", True),
    ("전 연령", None),
    ("만 14세 미만 사용 금지", False),
    ("어린이부터 성인까지", True),
    ("성인 및 어린이 겸용", True),
    ("", None),
])
def test_만_13세_이하를_포함하는지_판정한다(text, expected):
    assert child_state(text) is expected


def test_연령_표기끼리_어긋나면_충돌로_본다():
    assert combined_child_state(["3세 이상", "36개월 이상"]) == (True, False)
    assert combined_child_state(["3세 이상", "14세 이상"]) == (None, True)
    assert combined_child_state([]) == (None, False)


@pytest.mark.parametrize("value,quote,expected", [
    ("3세", "만 3세 이상", True),
    ("3세", "13세 이상", False),
    ("13세 이상", "만 13세 이상 권장", True),
    ("3 세", "3세 이상", True),
])
def test_연령_값이_숫자_중간에서_잘리지_않았는지_본다(value, quote, expected):
    assert age_value_bounded(value, quote) is expected


def test_판매_안내는_조건부이고_구매대행과_사입을_나누지_않는다():
    action = sale_action(Scheme.CONFIRMATION, "완구")
    assert action.startswith("[완구 · 안전확인 후보] 이 품목으로 분류되면")
    assert "KC 안전확인 신고" in action and "구매대행·사입 모두" in action
