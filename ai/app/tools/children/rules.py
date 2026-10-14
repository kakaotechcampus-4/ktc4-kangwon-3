"""어린이제품 Tool의 코드 규칙과 판매 안내 문구. 모델을 부르지 않는 순수 함수만 둔다.

- 연령 규칙: 상품 원문의 연령 표기를 개월 범위로 읽어 법 제2조 제1호의 "만 13세 이하"를 포함하는지 본다.
- 제외 물품: 법 제2조 제1호 단서의 물품(의약품·의료기기·화장품·식품용 기구 등) 이름 목록.
- 판매 안내: 제도별로 판매 전에 확인할 일. 품목 분류가 후보이므로 모두 조건부로 쓴다.
"""

import re
from dataclasses import dataclass

from .evidence import Scheme

CHILD_LIMIT_MONTHS = 13 * 12 + 11

_UNIT = r"(개월|세(?!트)|살)"
_RANGE_RE = re.compile(rf"(\d{{1,3}})\s*{_UNIT}?\s*(?:~|∼|-|–|부터)\s*(?:만\s*)?(\d{{1,3}})\s*{_UNIT}\s*(이하|미만|까지)?")
_SINGLE_RE = re.compile(rf"(\d{{1,3}})\s*{_UNIT}\s*(이상|이하|미만|초과|부터|까지|\+)?")
_PLUS_RE = re.compile(r"(?<!\d)(\d{1,2})\s*\+")
_PROHIBITION_RE = re.compile(r"금지|불가|사용할\s*수\s*없|사용하지\s*마|부적합")
_ADULT_WORDS = ("성인", "어른")
_CHILD_WORDS = ("영아", "유아", "아동", "어린이", "키즈", "유치원", "초등", "신생아", "아기")

EXCLUDED_KINDS = ("의약품", "의약외품", "의료기기", "화장품", "식품용 기구", "식품 용기·포장", "테마파크시설")


@dataclass(frozen=True)
class AgeRange:
    """개월 단위 사용 연령 범위. None은 제한 없음."""

    min_months: int | None
    max_months: int | None


def _months(number: str, unit: str | None) -> int:
    value = int(number)
    return value if unit == "개월" else value * 12


def parse_age(text: str) -> AgeRange | None:
    """연령 표기 하나를 개월 범위로 읽는다. 읽을 수 없으면 None.

    "만 3세 이상", "36개월 미만", "3~7세", "6개월~3세", "14세 이상", "8+" 같은 표기를 읽는다.
    "N세 이하"는 만 N세까지(N세 11개월)를 포함한다(운용요령 완구 적용범위의 연령 해석과 같다).
    사용 금지 문구("N세 미만 사용 금지")는 반대로 "N세 이상"으로 읽고, 그 밖의 금지 문구는 읽지 않는다.
    """
    text = text.strip()
    if _PROHIBITION_RE.search(text):
        match = _SINGLE_RE.search(text)
        if match and match.group(3) == "미만":
            return AgeRange(_months(match.group(1), match.group(2)), None)
        return None
    match = _RANGE_RE.search(text)
    if match:
        low_number, low_unit, high_number, high_unit, high_op = match.groups()
        low = _months(low_number, low_unit or high_unit)
        high = _months(high_number, high_unit)
        if high_op == "미만":
            high -= 1
        elif high_unit != "개월":
            high += 11
        return AgeRange(low, high)
    match = _SINGLE_RE.search(text)
    if match:
        number, unit, op = match.groups()
        months = _months(number, unit)
        if op in ("이상", "부터", "+"):
            return AgeRange(months, None)
        if op == "초과":
            return AgeRange(months + (1 if unit == "개월" else 12), None)
        if op == "미만":
            return AgeRange(None, months - 1)
        if op in ("이하", "까지"):
            return AgeRange(None, months + (0 if unit == "개월" else 11))
        return AgeRange(months, months + (0 if unit == "개월" else 11))
    match = _PLUS_RE.search(text)
    if match:
        return AgeRange(int(match.group(1)) * 12, None)
    return None


def child_state(text: str) -> bool | None:
    """연령 표기 하나가 만 13세 이하를 포함하는지. True 포함, False 미포함, None 판단 불가.

    숫자 범위를 먼저 보고, 숫자가 없으면 "성인"·"유아" 같은 낱말을 본다. 미포함도 확정이 아니라
    "어린이제품이 아닐 가능성"이다.
    """
    age = parse_age(text)
    if age is not None:
        return age.min_months is None or age.min_months <= CHILD_LIMIT_MONTHS
    adult = any(word in text for word in _ADULT_WORDS)
    child = any(word in text for word in _CHILD_WORDS)
    if child:
        return True
    if adult:
        return False
    return None


def age_value_bounded(value: str, quote: str) -> bool:
    """연령 값이 인용 안에서 숫자 중간부터 잘린 값이 아닌지("13세 이상"의 "3세" 방지)."""
    value, quote = "".join(value.split()), "".join(quote.split())
    start = quote.find(value)
    while start != -1:
        if start == 0 or not quote[start - 1].isdigit():
            return True
        start = quote.find(value, start + 1)
    return False


def combined_child_state(texts: list[str]) -> tuple[bool | None, bool]:
    """여러 연령 표기를 합친다. Returns: (상태, 충돌 여부). 읽은 값끼리 다르면 충돌이다."""
    states = {state for state in (child_state(text) for text in texts) if state is not None}
    if len(states) > 1:
        return None, True
    return (states.pop() if states else None), False


KC_ACTION = {
    Scheme.CERTIFICATION: "KC 안전인증을 받은 제품인지 인증번호로",
    Scheme.CONFIRMATION: "KC 안전확인 신고가 된 제품인지 신고번호로",
    Scheme.SUPPLIER: "공급자적합성확인(공통·개별 안전기준 시험)과 KC 표시가 된 제품인지",
}


def sale_action(scheme: Scheme, name: str) -> str:
    """후보 품목 기준으로 판매 전에 할 일. 어린이제품법에서 구매대행 특례 조문은 찾지 못해 판매 방식을 나누지 않는다."""
    return (f"[{name} · {scheme.value} 후보] 이 품목으로 분류되면 판매 전 {KC_ACTION[scheme]} 확인해야 합니다. "
            "구매대행·사입 모두 해당합니다.")
