"""판단 선택 코드 규칙. 판단 모델 없이 상품 정보만으로 선택이 정해지는 Tool과 걸린 규칙.

통관 항상 선택(원칙 3), true 필드, 모순 시 정보 부족(원칙 6), 상품을 모를 때 정보 부족(원칙 1),
전기 제품 무선 정보 없음(원칙 2) 순.
"""

from ...schemas.product import Product
from ...schemas.schemas import ToolName

# 항상 선택 (선택 프롬프트 원칙 3)
ALWAYS_SELECTED: dict[ToolName, str] = {ToolName.CUSTOMS: "해외 직구 상품은 수입 통관 대상"}

# 하나라도 true면 선택하는 필드 (선택 프롬프트 표 기준)
TRUE_FIELDS: dict[ToolName, tuple[str, ...]] = {
    ToolName.RADIO: ("wireless_comm", "wireless_charging", "wireless_shield"),
    ToolName.FOOD_DRUG: ("food_contact", "medical_claim", "cosmetic_claim"),
    ToolName.ELECTRICAL: ("electrical_powered", "battery_included", "battery_is_the_product", "heating"),
    ToolName.CHILDREN: ("for_children",),
}

# 원칙 1용 상품 식별 필드. 모두 None이면 어떤 상품인지 모름
_PRODUCT_IDENTITY_FIELDS = ("product_name", "category", "intended_use")

# 원칙 2용 전기 제품 신호
_ELECTRIC_FIELDS = ("electrical_powered", "battery_included")
# 원칙 2에서 None을 보는 무선 필드. wireless_shield는 추출 후처리로 false가 늘 None이 되어 제외 (판단 질문이 맡음)
_UNKNOWN_WIRELESS_FIELDS = ("wireless_comm", "wireless_charging")


def rule_reasons(product: Product) -> dict[ToolName, list[str]]:
    """코드 규칙에 걸린 Tool과 걸린 규칙 설명을 모은다.

    Args:
        product: 추출된 상품 정보.

    Returns:
        dict[ToolName, list[str]]: 규칙으로 선택되는 Tool별 규칙 설명. 걸리지 않은 Tool은 없음.
    """
    reasons = {name: [text] for name, text in ALWAYS_SELECTED.items()}
    for name, fields in TRUE_FIELDS.items():
        hits = [f"{field}=true" for field in fields if getattr(product, field) is True]
        if hits:
            reasons[name] = hits
    for name, reason in _conflict_reasons(product).items():
        reasons.setdefault(name, [reason])
    for name, reason in _unknown_product_reasons(product).items():
        reasons.setdefault(name, [reason])
    if ToolName.RADIO not in reasons and (reason := _radio_unknown_reason(product)):
        reasons[ToolName.RADIO] = [reason]
    return reasons


def _conflict_reasons(product: Product) -> dict[ToolName, str]:
    """원칙 6: 상품 정보에 모순이 있으면 관련 필드가 전부 None인 Tool을 정보 부족으로 선택.

    모순 문장이 어느 Tool과 관련 있는지는 보지 않음. 모순으로 칸을 비운 Tool을 놓치지 않는 쪽을 택함.

    Args:
        product: 추출된 상품 정보.

    Returns:
        dict[ToolName, str]: 규칙에 걸린 Tool별 규칙 설명. 모순이 없으면 빈 dict.
    """
    if not product.conflicts:
        return {}
    return {
        name: f"conflicts 있음, {'·'.join(fields)}=None (상품 정보 모순으로 정보 부족)"
        for name, fields in TRUE_FIELDS.items()
        if all(getattr(product, field) is None for field in fields)
    }


def _unknown_product_reasons(product: Product) -> dict[ToolName, str]:
    """원칙 1: 어떤 상품인지 모르면(상품명·종류·용도 모두 없음) 관련 필드가 전부 None인 Tool을 정보 부족으로 선택.

    판단 모델은 정보가 없으면 해당 가능성을 낮게 봐 미선택하므로 코드로 막음.

    Args:
        product: 추출된 상품 정보.

    Returns:
        dict[ToolName, str]: 규칙에 걸린 Tool별 규칙 설명. 상품을 알 수 있으면 빈 dict.
    """
    if any(getattr(product, field) is not None for field in _PRODUCT_IDENTITY_FIELDS):
        return {}
    return {
        name: f"{'·'.join(_PRODUCT_IDENTITY_FIELDS)}·{'·'.join(fields)}=None (어떤 상품인지 몰라 정보 부족)"
        for name, fields in TRUE_FIELDS.items()
        if all(getattr(product, field) is None for field in fields)
    }


def _radio_unknown_reason(product: Product) -> str | None:
    """원칙 2: 전기 제품인데 무선 필드가 None이면 정보 부족으로 전파 선택.

    Args:
        product: 추출된 상품 정보.

    Returns:
        str | None: 규칙 설명. 해당 없으면 None.
    """
    electric = [field for field in _ELECTRIC_FIELDS if getattr(product, field) is True]
    unknown = unknown_wireless_fields(product)
    if not electric or not unknown:
        return None
    return f"{'·'.join(electric)}=true인데 {'·'.join(unknown)}=None (전기 제품의 무선 기능 정보 없음)"


def unknown_wireless_fields(product: Product) -> list[str]:
    """값이 None인 무선 필드 (wireless_shield 제외).

    Args:
        product: 추출된 상품 정보.

    Returns:
        list[str]: None인 무선 필드 이름. 없으면 빈 목록.
    """
    return [field for field in _UNKNOWN_WIRELESS_FIELDS if getattr(product, field) is None]
