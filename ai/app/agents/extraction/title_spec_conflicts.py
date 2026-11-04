"""제목·옵션명과 스펙표가 같은 항목을 다르게 적은 모순을 규칙으로 찾는다.

모델(gpt-4.1-mini)은 스펙표가 맞겠거니 하고 제목을 넘겨 제목↔스펙표 모순을 거의 보고하지 않는다
(초안 50건 측정, 2026-11-05: 12건 중 0건. 프롬프트를 두 번 보강해도 같음). 자주 나온 유형만 규칙으로 잡는다.

- 사용 대상 성별: 제목 "남성용"인데 스펙표 "남녀공용"
- 연령 범위: 제목 "0-2 세"인데 스펙표 "1~3세"
- 단위 붙은 수치(L·ml·mAh·mWh·W): 제목 "635L"인데 스펙표 "60L 미만", 제목 안의 "4255mWh"와 "4225mWh"
- 재질: 제목 "구리 합금"인데 스펙표 성분에 구리가 없음
- 전원 방식: 스펙표 "전자식: 아니요"인데 "전원 공급: 교류", 제목 "충전식"인데 "전원 공급: 전기 없음"
- 계절: 제목 "봄/여름용"인데 스펙표 "계절: 봄/가을"

검토 후보일 뿐 모델 값을 덮어쓰지 않는다. 문장에는 양쪽 표기를 원문 그대로 넣어 사람이 바로 대조할 수 있게 한다.
"""

import re
from collections.abc import Iterable

# --- 스펙표 읽기 ---------------------------------------------------------------
# 알리·테무 스펙표는 "키" 줄 다음에 "값" 줄이 온다. 테무 옵션은 "키: 값" 한 줄이다.
_INLINE_ROW = re.compile(r"^([^:：]{1,30})[:：]\s*(\S.*)$")


def _spec_rows(text_blocks: Iterable[str]) -> list[tuple[str, str]]:
    """스펙표를 (키, 값) 목록으로 읽는다. 키에 붙은 ':'는 뗀다."""
    rows: list[tuple[str, str]] = []
    for block in text_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            inline = _INLINE_ROW.match(line)
            if inline:
                rows.append((inline.group(1).strip(), inline.group(2).strip()))
            elif index + 1 < len(lines):
                rows.append((line.rstrip(":：").strip(), lines[index + 1]))
    return rows


def _values_for(rows: list[tuple[str, str]], key_pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    return [(key, value) for key, value in rows if key_pattern.search(key)]


def _sentence(title_text: str, key: str, value: str) -> str:
    return f'제목은 "{title_text}"인데 스펙표 {key}은 "{value}"입니다. 판매자 표기가 서로 달라 확인이 필요합니다.'


# --- 1. 사용 대상 성별 -----------------------------------------------------------
_TITLE_GENDER = re.compile(r"(남성|여성|남아|여아)용")
_GENDER_KEY = re.compile(r"성별|대상")
_UNISEX = re.compile(r"남녀\s*공용|유니섹스|unisex", re.IGNORECASE)


def _gender_conflicts(titles: list[str], rows: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for title in titles:
        match = _TITLE_GENDER.search(title)
        if not match:
            continue
        for key, value in _values_for(rows, _GENDER_KEY):
            if _UNISEX.search(value):
                found.append(_sentence(match.group(0), key, value))
    return found


# --- 2. 연령 범위 ----------------------------------------------------------------
# "0-2 세", "1~3세", "3세 이상", "3년 이상", "Ages 3+", "3-6Y". 개월(M)은 세와 섞어 비교하지 않는다.
_AGE_RANGE = re.compile(r"(\d{1,2})\s*[-~]\s*(\d{1,2})\s*(세|살|년|Y)\b", re.IGNORECASE)
_AGE_LOWER = re.compile(r"(\d{1,2})\s*(?:(?:세|살|년)\s*이상|\+)", re.IGNORECASE)
_AGE_KEY = re.compile(r"연령|나이|age", re.IGNORECASE)


def _age(text: str) -> tuple[str, int, int | None] | None:
    """(원문 표기, 하한, 상한)을 돌려준다. 못 찾으면 None."""
    match = _AGE_RANGE.search(text)
    if match:
        return match.group(0), int(match.group(1)), int(match.group(2))
    match = _AGE_LOWER.search(text)
    if match:
        return match.group(0), int(match.group(1)), None
    return None


def _age_conflicts(titles: list[str], rows: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for title in titles:
        title_age = _age(title)
        if not title_age:
            continue
        for key, value in _values_for(rows, _AGE_KEY):
            spec_age = _age(value)
            if not spec_age:
                continue
            lower_differs = title_age[1] != spec_age[1]
            upper_differs = title_age[2] is not None and spec_age[2] is not None and title_age[2] != spec_age[2]
            if lower_differs or upper_differs:
                found.append(_sentence(title_age[0], key, value))
    return found


# --- 3. 단위 붙은 수치 --------------------------------------------------------------
# 전압·치수처럼 범위로 적는 단위는 뺀다("100-240V"에 "220V"는 모순이 아니다).
# "10000/20000mAh"처럼 '/'로 나열한 값은 단위를 함께 쓴 것으로 보고 전부 담는다.
_UNIT_NUMBER = re.compile(r"((?:\d+(?:\.\d+)?\s*/\s*)*\d+(?:\.\d+)?)\s*(mAh|mWh|ml|L|W)(?![A-Za-z])")


def _unit_numbers(text: str) -> dict[str, list[tuple[str, str]]]:
    """단위별 (원문 표기, 숫자) 목록."""
    by_unit: dict[str, list[tuple[str, str]]] = {}
    for match in _UNIT_NUMBER.finditer(text):
        unit_key = match.group(2).lower()
        for number in re.split(r"\s*/\s*", match.group(1)):
            by_unit.setdefault(unit_key, []).append((match.group(0), number))
    return by_unit


def _one_digit_apart(a: str, b: str) -> bool:
    """가운데 한 자리만 다른 값("4255"와 "4225")인지. 앞자리가 다른 값("10000"과 "20000")은 다른 규격이다."""
    if len(a) != len(b):
        return False
    differing = [index for index, (x, y) in enumerate(zip(a, b)) if x != y]
    return len(differing) == 1 and differing[0] != 0


def _number_conflicts(titles: list[str], spec_text: str) -> list[str]:
    found: list[str] = []
    spec_units = _unit_numbers(spec_text)
    for title in titles:
        for unit, items in _unit_numbers(title).items():
            # 제목 안에서 한 자리만 다른 두 값("4255mWh"와 "4225mWh")은 오타 모순이다.
            numbers = [number for _, number in items]
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    # "10000/20000mAh"처럼 한 표기 안에 나열한 값은 규격 선택지라 모순이 아니다.
                    if items[i][0] == items[j][0]:
                        continue
                    if numbers[i] != numbers[j] and _one_digit_apart(numbers[i], numbers[j]):
                        found.append(
                            f'제목 안에 "{items[i][0]}"와 "{items[j][0]}"가 함께 있습니다. 판매자 표기가 서로 달라 확인이 필요합니다.'
                        )
            spec_items = spec_units.get(unit)
            if not spec_items:
                continue
            spec_numbers = {number for _, number in spec_items}
            if any(number in spec_numbers for number in numbers):
                continue
            spec_text_list = ", ".join(f'"{text}"' for text, _ in spec_items)
            found.append(
                f'제목은 "{items[0][0]}"인데 스펙표에는 {spec_text_list}로 적혀 있습니다. 판매자 표기가 서로 달라 확인이 필요합니다.'
            )
    return found


# --- 4. 재질 -------------------------------------------------------------------------
_MATERIAL_KEY = re.compile(r"소재|재질|재료|성분|material", re.IGNORECASE)
# 제목에서 찾을 재질 표기 → 스펙표에서 같은 재질로 볼 표기
_MATERIAL_SYNONYMS: dict[str, re.Pattern[str]] = {
    "구리": re.compile(r"구리|copper|동\b", re.IGNORECASE),
    "가죽": re.compile(r"가죽|leather", re.IGNORECASE),
    "순면": re.compile(r"면|cotton|코튼", re.IGNORECASE),
    "면": re.compile(r"면|cotton|코튼", re.IGNORECASE),
    "원목": re.compile(r"나무|원목|목재|wood|우드", re.IGNORECASE),
    "나무": re.compile(r"나무|원목|목재|wood|우드", re.IGNORECASE),
    "대나무": re.compile(r"대나무|bamboo", re.IGNORECASE),
    "유리": re.compile(r"유리|glass", re.IGNORECASE),
    "스테인리스": re.compile(r"스테인리스|stainless|스틸|steel", re.IGNORECASE),
    "실리콘": re.compile(r"실리콘|silicone|silica", re.IGNORECASE),
    "세라믹": re.compile(r"세라믹|도자기|ceramic", re.IGNORECASE),
    "티크": re.compile(r"티크|teak", re.IGNORECASE),
    "라탄": re.compile(r"라탄|등나무|rattan", re.IGNORECASE),
    "실크": re.compile(r"실크|silk|견", re.IGNORECASE),
}
_TITLE_MATERIAL = re.compile("|".join(sorted(_MATERIAL_SYNONYMS, key=len, reverse=True)))


def _material_conflicts(titles: list[str], rows: list[tuple[str, str]]) -> list[str]:
    material_rows = _values_for(rows, _MATERIAL_KEY)
    if not material_rows:
        return []
    found: list[str] = []
    for title in titles:
        for match in _TITLE_MATERIAL.finditer(title):
            synonyms = _MATERIAL_SYNONYMS[match.group(0)]
            if any(synonyms.search(value) for _, value in material_rows):
                continue
            key, value = material_rows[0]
            found.append(_sentence(match.group(0), key, value))
            break  # 제목 재질 하나만 보고해도 사람이 대조하기엔 충분하다
    return found


# --- 5. 전원 방식 -----------------------------------------------------------------------
_ELECTRIC_KEY = re.compile(r"전자식|전동")
_NO = re.compile(r"아니요|아니오|no\b|없음", re.IGNORECASE)
_POWER_KEY = re.compile(r"전원|전압|전력")
_POWERED_VALUE = re.compile(r"교류|직류|AC|DC|\d+\s*V|USB|배터리|전지|충전|콘센트", re.IGNORECASE)
_NO_POWER_VALUE = re.compile(r"전기\s*없음|전기가\s*없는|없음|해당\s*없음|비전동|수동")
# 뜻이 분명한 표기부터 본다. "비전동"·"무전원"은 전기 제품이 아니라는 말이라 뺀다.
_TITLE_POWERED = (
    re.compile(r"충전식"),
    re.compile(r"(?<!비)전동"),
    re.compile(r"(?<!무)전기(?!\s*없)"),
    re.compile(r"배터리"),
    re.compile(r"USB", re.IGNORECASE),
)


def _title_powered(title: str) -> str | None:
    for pattern in _TITLE_POWERED:
        match = pattern.search(title)
        if match:
            return match.group(0)
    return None


def _power_conflicts(titles: list[str], rows: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    electric_no = [(key, value) for key, value in _values_for(rows, _ELECTRIC_KEY) if _NO.search(value)]
    power_rows = _values_for(rows, _POWER_KEY)
    powered = [(key, value) for key, value in power_rows if _POWERED_VALUE.search(value) and not _NO_POWER_VALUE.search(value)]
    if electric_no and powered:
        (key, value), (power_key, power_value) = electric_no[0], powered[0]
        found.append(
            f'스펙표 {key}은 "{value}"인데 {power_key}은 "{power_value}"입니다. 판매자 표기가 서로 달라 확인이 필요합니다.'
        )
    unpowered = [(key, value) for key, value in power_rows if _NO_POWER_VALUE.search(value)]
    for title in titles:
        powered_text = _title_powered(title)
        if not powered_text:
            continue
        for key, value in unpowered:
            found.append(_sentence(powered_text, key, value))
    return found


# --- 6. 계절 ----------------------------------------------------------------------------
_SEASON_WORDS = ("봄", "여름", "가을", "겨울")
_TITLE_SEASON = re.compile(r"((?:봄|여름|가을|겨울)(?:\s*[/·,]\s*(?:봄|여름|가을|겨울))*)\s*용")
_SEASON_KEY = re.compile(r"계절|시즌|season", re.IGNORECASE)


def _seasons(text: str) -> set[str]:
    return {word for word in _SEASON_WORDS if word in text}


def _season_conflicts(titles: list[str], rows: list[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for title in titles:
        match = _TITLE_SEASON.search(title)
        if not match:
            continue
        for key, value in _values_for(rows, _SEASON_KEY):
            spec_seasons = _seasons(value)
            if spec_seasons and spec_seasons != _seasons(match.group(1)):
                found.append(_sentence(match.group(1), key, value))
    return found


def detect_title_spec_conflicts(titles: list[str], text_blocks: list[str]) -> list[str]:
    """제목·옵션명과 스펙표가 같은 항목을 다르게 적은 모순 후보를 돌려준다.

    Args:
        titles: 판매자 제목(판매자 구역에서 찾은 것).
        text_blocks: 판매자 구역 원문 블록(스펙표 포함).

    Returns:
        list[str]: 모순 후보 문장. 양쪽 표기를 원문 그대로 담는다. 없으면 빈 목록.
    """
    rows = _spec_rows(text_blocks)
    spec_text = "\n".join(text_blocks)
    found: list[str] = []
    for conflicts in (
        _gender_conflicts(titles, rows),
        _age_conflicts(titles, rows),
        _number_conflicts(titles, spec_text),
        _material_conflicts(titles, rows),
        _power_conflicts(titles, rows),
        _season_conflicts(titles, rows),
    ):
        for sentence in conflicts:
            if sentence not in found:
                found.append(sentence)
    return found
