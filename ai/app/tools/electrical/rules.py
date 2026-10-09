"""전기 Tool의 코드 규칙과 판매 안내 문구. LLM을 부르지 않는 순수 함수만 둔다.

- 법령 제외 규칙: 저전압 제외(운용요령 제3조), 전지 전용 구조 제외(운용요령 별표 공통 비고)
- 오답 감소용 후보 필터: 전기저장장치 구성품 (법령 제외 규칙이 아니다)
- 구매대행 특례(법 제35조, 시행규칙 별표 13) 안내 문구. 품목 분류가 후보이므로 모두 조건부로 쓴다.
"""

import re

from ...schemas.electrical import ElectricalFact
from ...schemas.product import Product
from .evidence import AnnexBlock, compact

# 법제처 별표는 표 테두리 문자(─│┌ 등, U+2500–257F)가 줄바꿈 자리마다 끼어 온다.
# 공백만 지우면 모델이 정확히 이어 쓴 인용도 원문과 다르다고 판정한다.
_BOX_DRAWING = {code: None for code in range(0x2500, 0x2580)}
_VOLTAGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Vv](?![A-Za-z])")


def normal_text(text: str) -> str:
    return "".join(text.translate(_BOX_DRAWING).split())


def low_voltage(facts: dict[str, list[ElectricalFact]]) -> tuple[bool | None, str | None]:
    """운용요령 제3조의 저전압(교류 30V·직류 42V 이하) 여부를 명시된 값으로만 판정한다.

    Returns:
        (저전압 여부, "AC"/"DC"). 전류 종류나 전압이 없거나 값이 여러 개면 (None, …).
    """
    texts = [fact.value for field in ("power_source", "rated_voltage") for fact in facts.get(field, [])]
    joined = " ".join(texts).upper()
    is_ac = "AC" in joined or "교류" in joined
    is_dc = "DC" in joined or "직류" in joined or "USB" in joined
    current = "AC" if is_ac and not is_dc else "DC" if is_dc and not is_ac else None
    volts = {float(match) for text in texts for match in _VOLTAGE_RE.findall(text)}
    if current is None or len(volts) != 1:
        return None, current
    limit = 30 if current == "AC" else 42
    return next(iter(volts)) <= limit, current


def excluded_by_low_voltage(block: AnnexBlock, low: bool | None, current: str | None) -> bool:
    """저전압 제품인데 그 행의 비고가 저전압을 포함한다고 정하지 않았으면 제외 대상이다."""
    if low is not True:
        return False
    return not (block.includes_low_voltage_ac if current == "AC" else block.includes_low_voltage_dc)


ESS_WORDS = ("전기저장장치", "에너지저장장치", "ESS", "전지시스템")


def is_ess_component(block: AnnexBlock) -> bool:
    return "전기저장장치" in compact(block.category)


# 전지 전용 구조 제외(공통 비고)가 적용되지 않는 행: 전지 자체, 충전기·전원장치, 공통 비고의 예외인 전격살충기.
BATTERY_OR_SUPPLY_WORDS = ("전지", "충전기", "직류전원장치", "어댑터", "전격살충기")
BATTERY_HINT_WORDS = ("충전", "배터리", "전지", "건전지", "무선", "코드리스")
BATTERY_SEARCH_TERMS = ("충전지 전지", "전지 충전기", "직류전원장치")


def battery_only_state(facts: dict[str, list[ElectricalFact]]) -> bool | None:
    values = {fact.value.strip() for fact in facts.get("battery_only", [])}
    return True if values == {"예"} else False if values == {"아니오"} else None


def is_battery_or_supply(block: AnnexBlock) -> bool:
    names = compact(" ".join((*block.items, *block.sub_items)))
    return any(word in names for word in BATTERY_OR_SUPPLY_WORDS)


def mentions_battery(facts: dict[str, list[ElectricalFact]], product: Product) -> bool:
    texts = compact(" ".join(f.value + f.quote for field in ("power_source", "product_type")
                             for f in facts.get(field, [])))
    return product.battery_included is True or any(word in texts for word in BATTERY_HINT_WORDS)


# 결과 요약에 붙일 구매대행 특례 문구(법 제35조, 시행규칙 별표 13).
# 품목 분류 자체가 후보이므로 모든 안내는 조건부로 쓴다("해당 품목으로 분류되면 …").
# 특례 목록에서 이름을 찾지 못한 것은 "특례 없음"이 아니라 "대응 미확인"이다.
PURCHASE_SUMMARY = {
    "listed": "이 품목으로 분류되면 구매대행 특례(시행규칙 별표 13) 대상이라 구매대행은 KC 표시 없이 가능하고, "
              "사입·수입 판매는 KC가 필요합니다.",
    "listed_with_exclusion": "이 품목으로 분류되고 특례 목록의 제외 조건에 해당하지 않으면 구매대행 특례(시행규칙 별표 13)를 "
                             "적용할 수 있습니다. 제외 조건 해당 여부는 확인이 필요합니다.",
    "unmatched": "구매대행 특례 목록(시행규칙 별표 13)에서 이 품목명을 찾지 못했습니다. 특례 해당 여부는 확인이 필요합니다.",
    "similar_clause": "구매대행 특례의 '그 밖에 유사한 기기' 해당 여부는 확인이 필요합니다.",
    "unknown": "판매 방식별 의무는 확인이 필요합니다.",
}


def sale_actions(block: AnnexBlock, status: str, listed_as: str) -> list[str]:
    """후보 품목 기준으로 판매 전에 해야 할 일. 판매 방식(구매대행/사입)은 사용자가 정한다."""
    scheme = block.scheme.value
    label = f"[{item_name(block)} · {scheme} 후보]"
    kc = "KC 안전인증" if scheme == "안전인증" else "KC 안전확인 신고" if scheme == "안전확인" else "공급자적합성확인"
    import_action = f"{label} 사입·수입 판매: 판매 전 {kc}를 받은 제품인지 공급사 인증·신고 번호로 확인해야 합니다."
    if status == "listed":
        return [
            f"{label} 구매대행: 이 품목으로 분류되면 구매대행 특례(시행규칙 별표 13) 대상이라 KC 표시 없이 "
            "구매대행할 수 있습니다. 이 경우 구매대행업자의 고지 의무(법 제36조)를 지켜야 합니다.",
            import_action,
        ]
    if status == "listed_with_exclusion":
        return [
            f"{label} 구매대행: 이 품목으로 분류되고 특례 목록의 제외 조건('{listed_as}')에 해당하지 않으면 "
            "구매대행 특례를 적용할 수 있습니다. 제외 조건에 해당하면 구매대행도 "
            f"{kc}를 받은 제품만 판매할 수 있습니다. 제외 조건 해당 여부를 먼저 확인해야 합니다.",
            import_action,
        ]
    if status == "unmatched":
        return [
            f"{label} 구매대행: 특례 목록(시행규칙 별표 13)에서 이 품목명을 찾지 못했습니다. 특례 해당 여부를 "
            f"확인하기 전까지는 {kc}를 받은 제품만 판매하는 것이 안전합니다.",
            import_action,
        ]
    if status == "similar_clause":
        return [f"{label} 구매대행 특례의 '그 밖에 유사한 기기' 해당 여부는 확인이 필요합니다. "
                f"사입·수입 판매는 {kc}를 받은 제품인지 확인해야 합니다."]
    if block.scheme.value == "공급자적합성확인":
        return [f"{label} 사입·수입 판매 시 공급자적합성확인과 KC 표시가 필요합니다. 구매대행 시 의무는 확인이 필요합니다."]
    return [f"{label} 판매 전 {kc} 여부를 확인해야 합니다."]




def item_name(block: AnnexBlock) -> str:
    return re.sub(r"^[가-힣]\s*\.\s*", "", block.items[0]) if block.items else block.category
