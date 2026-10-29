"""식약 Tool의 판매 안내 문구. LLM을 부르지 않는 순수 함수만 둔다.

분류 자체가 후보이므로 모든 안내는 조건부로 쓴다("이 품목으로 분류되면 …", "식품용 기구라면 …").
판매 방식(구매대행/사입)은 상품 글에서 알 수 없어 두 경우의 할 일을 함께 낸다.
"""

from .evidence import BannedIngredient, DeviceItem, FunctionalType


def imported_food_actions(product: str, kind: str) -> list[str]:
    """수입식품등(식품·건강기능식품·식품용 기구)의 수입 판매 안내. 근거는 수입식품안전관리 특별법이다.

    Args:
        product: 안내 꼬리표에 쓸 상품 이름.
        kind: 안내 꼬리표에 쓸 분류. 예: "식품용 기구", "식품".

    Returns:
        list[str]: 사입·수입 판매 안내와 구매대행 안내.
    """
    label = f"[{product} · {kind} 후보]"
    return [
        f"{label} 사입·수입 판매: 수입식품등 수입·판매업 영업등록(수입식품안전관리 특별법 제14조 제1항 제1호, 제15조) 후 "
        "판매 목적으로 수입할 때마다 수입신고를 해야 합니다(같은 법 제20조 제1항).",
        f"{label} 구매대행: 수입식품등 인터넷 구매 대행업 영업등록이 필요합니다(같은 법 제14조 제1항 제3호, 제15조, "
        "시행령 제2조 제3호). 구매대행 수입분의 수입신고 대상 여부는 확인이 필요합니다(같은 법 제20조 제1항).",
    ]


def health_food_action(product: str, claims: list[str]) -> str:
    """먹는 상품에 기능성 표방 문구가 있는 경우(건강기능식품에 관한 법률 제3조).

    Args:
        product: 안내 꼬리표에 쓸 상품 이름.
        claims: 기능성 표방 문구.

    Returns:
        str: 건강기능식품 확인 안내.
    """
    quoted = ", ".join(f"'{claim}'" for claim in claims)
    return (f"[{product} · 기능성 표방 {quoted}] 건강기능식품으로 판매하려면 인체에 유용한 기능성을 가진 원료로 제조한 "
            "건강기능식품이어야 합니다(건강기능식품에 관한 법률 제3조). 일반 식품이면 기능성 표방 문구는 표시·광고 "
            "Tool 결과와 함께 확인이 필요합니다.")


def cosmetic_actions(product: str) -> list[str]:
    """화장품(화장품법 제2조 제1호)의 판매 안내. 수입대행형 거래 알선도 화장품책임판매업이다(제2조 제11호).

    Args:
        product: 안내 꼬리표에 쓸 상품 이름.

    Returns:
        list[str]: 사입·수입 판매 안내와 구매대행 안내.
    """
    label = f"[{product} · 화장품 후보]"
    return [
        f"{label} 사입·수입 판매: 수입 화장품을 유통·판매하려면 화장품책임판매업 등록이 필요합니다(화장품법 제3조 제1항). "
        "책임판매관리자를 두고 품질관리·책임판매 후 안전관리 기준을 갖춰야 합니다(같은 조 제3항).",
        f"{label} 구매대행: 수입대행형 거래를 목적으로 화장품을 알선·수여하는 것도 화장품책임판매업이라 등록이 필요합니다"
        "(화장품법 제2조 제11호, 제3조 제1항).",
    ]


def functional_action(product: str, types: list[FunctionalType]) -> str:
    """기능성화장품 표방(화장품법 제4조, 제15조 제1호).

    Args:
        product: 안내 꼬리표에 쓸 상품 이름.
        types: 대응한 기능성화장품 범위.

    Returns:
        str: 심사·보고 안내.
    """
    numbers = ", ".join(f"제{item.number}호" for item in types)
    return (f"[{product} · 기능성화장품 후보(시행규칙 제2조 {numbers})] 기능성화장품으로 판매하려면 품목별로 안전성·유효성 "
            "심사를 받거나 보고서를 제출해야 합니다(화장품법 제4조 제1항). 심사·보고 없는 기능성화장품은 판매하거나 "
            "수입대행을 알선할 수 없습니다(같은 법 제15조 제1호).")


def banned_action(ingredient: str, row: BannedIngredient) -> str:
    """사용할 수 없는 원료와 이름이 같은 성분(화장품법 제8조 제1항, 제15조 제5호).

    Args:
        ingredient: 상품의 성분명.
        row: 이름이 같은 원료 행.

    Returns:
        str: 판매 금지 안내. 조건부 원료면 조건 확인 안내.
    """
    if row.conditional:
        return (f"[성분 '{ingredient}' · 조건부 금지 원료 '{row.name}'] 원료가 이 조건에 해당하면 판매·수입대행 알선·진열을 "
                "할 수 없습니다(화장품법 제15조 제5호). 원료 규격서·시험성적서로 조건 해당 여부를 확인해야 합니다.")
    return (f"[성분 '{ingredient}' · 사용할 수 없는 원료 '{row.name}'] 이 원료를 사용한 화장품은 판매·수입대행 알선·"
            "진열을 할 수 없습니다(화장품법 제15조 제5호). 전성분표와 원료명을 확인해야 합니다.")


def device_actions(item: DeviceItem) -> list[str]:
    """의료기기 품목 후보의 판매 안내. 근거는 의료기기법 제15조·제17조·제26조, 시행규칙 제32조다.

    Args:
        item: 고른 의료기기 품목.

    Returns:
        list[str]: 사입·수입 판매 안내와 구매대행 안내.
    """
    label = f"[{item.name} · 의료기기 {item.grade}등급 후보]"
    return [
        f"{label} 사입·수입 판매: 이 품목으로 분류되면 의료기기 수입업허가와 품목 수입허가·인증·신고(의료기기법 제15조), "
        "판매업신고(같은 법 제17조)가 필요합니다. 허가·인증·신고 없는 의료기기는 판매·진열할 수 없습니다(같은 법 제26조 제1항).",
        f"{label} 구매대행: 소비자의 자가 사용용 수입은 수입허가 등이 면제될 수 있지만(시행규칙 제32조 제1항 제6호, "
        "식약처 고시 범위), 허가·인증·신고 없는 의료기기를 판매하거나 판매 목적으로 진열하는 것은 금지됩니다(법 제26조 제1항). "
        "구매대행으로 팔 수 있는지는 확인이 필요합니다.",
    ]


def claim_action(claims: list[str]) -> str:
    """의료기기로 분류되지 않았는데 효능 문구가 있는 경우(의료기기법 제26조 제7항).

    Args:
        claims: 효능 표방 문구.

    Returns:
        str: 오인 표시·광고 금지 안내.
    """
    quoted = ", ".join(f"'{claim}'" for claim in claims)
    return (f"[효능 표방 문구 {quoted}] 의료기기가 아니라면 의료기기와 비슷한 효능·효과로 오인될 표시·광고를 할 수 "
            "없습니다(의료기기법 제26조 제7항). 문구를 빼거나 의료기기 해당 여부를 먼저 확인해야 합니다.")
