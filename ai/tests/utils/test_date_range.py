"""기준일로부터 N년 이내 판정 유틸을 기준일을 고정해 검증한다."""

from datetime import date

import pytest

from app.utils.date_range import is_date_prefix_within_years, years_ago

TODAY = date(2026, 10, 12)


def test_N년_전_같은_날을_구한다():
    assert years_ago(5, TODAY) == date(2021, 10, 12)


def test_기준일이_윤일이고_N년_전이_평년이면_2월_28일로_맞춘다():
    assert years_ago(5, date(2024, 2, 29)) == date(2019, 2, 28)


@pytest.mark.parametrize(
    ("prefix", "within"),
    [
        # 경계 20211012와 같은 자릿수끼리 비교
        ("2021", True), ("202110", True), ("20211012", True),
        ("2020", False), ("202109", False), ("20211011", False),
        ("2026", True), ("2030", True),
    ],
)
def test_연_연월_연월일_검색값이_기간에_걸치는지_판정한다(prefix, within):
    assert is_date_prefix_within_years(prefix, 5, TODAY) is within


@pytest.mark.parametrize("prefix", ["2024-03", "24", "20240101~20241231", "", "2024031"])
def test_형식이_틀린_검색값은_예외를_올린다(prefix):
    with pytest.raises(ValueError):
        is_date_prefix_within_years(prefix, 5, TODAY)
