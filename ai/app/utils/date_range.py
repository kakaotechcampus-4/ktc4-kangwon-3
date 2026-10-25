"""기준일로부터 N년 이내인지 판정하는 날짜 유틸리티. 매 호출마다 오늘 날짜로 계산."""

import re
from datetime import date

# 연(YYYY)·연월(YYYYMM)·연월일(YYYYMMDD) 앞부분 일치 검색값
_DATE_PREFIX_RE = re.compile(r"\d{4}(?:\d{2}(?:\d{2})?)?")


def years_ago(years: int, today: date | None = None) -> date:
    """기준일에서 N년 전 날짜를 구한다.

    Args:
        years: 거슬러 올라갈 연수.
        today: 기준일. None이면 오늘.

    Returns:
        date: N년 전 같은 날. 기준일이 2월 29일이고 그 해가 윤년이 아니면 2월 28일.
    """
    today = today or date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def is_date_prefix_within_years(prefix: str, years: int, today: date | None = None) -> bool:
    """연·연월·연월일 검색값이 기준일로부터 N년 이내 기간에 걸치는지 판정한다.

    같은 자릿수끼리 비교함. 예: 기준일 2026-10-12, 5년이면 경계는 20211012이고
    "2021"·"202110"·"20211012"는 이내, "2020"·"202109"·"20211011"은 밖.

    Args:
        prefix: YYYY, YYYYMM, YYYYMMDD 형식 검색값.
        years: 허용 연수.
        today: 기준일. None이면 오늘.

    Returns:
        bool: N년 이내 기간에 걸치면 True.

    Raises:
        ValueError: YYYY, YYYYMM, YYYYMMDD 형식이 아닌 경우.
    """
    if not _DATE_PREFIX_RE.fullmatch(prefix):
        raise ValueError(f"날짜 검색값은 YYYY, YYYYMM, YYYYMMDD 형식이어야 함: {prefix!r}")
    cutoff = years_ago(years, today).strftime("%Y%m%d")
    return prefix >= cutoff[:len(prefix)]
