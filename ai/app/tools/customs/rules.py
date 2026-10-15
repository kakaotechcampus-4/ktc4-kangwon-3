"""통관 Tool의 코드 규칙과 판매 안내 문구. LLM을 부르지 않는 순수 함수만 둔다.

- HS 표기: 숫자 10자리 → "8516.79-9000", 6자리 → "8516.79".
- 요건 법령과 다른 규제 Tool의 대응(검증 단계가 교차 확인할 수 있게 결과에 남긴다).
- 판매 방식별 안내(관세법 제226조, 고시 별표 2·제7조 제2항). HS가 후보이므로 모두 조건부로 쓴다.
"""

from ...schemas.schemas import ToolName
from .evidence import ConfirmationRow, law_key

# 세관장확인 요건 법령 → 같은 법을 판단하는 규제 Tool. 키는 law_key(공백·가운뎃점 무시).
RELATED_TOOLS: dict[str, ToolName] = {
    law_key(name): tool for name, tool in (
        ("전기용품 및 생활용품 안전관리법", ToolName.ELECTRICAL),
        ("전파법", ToolName.RADIO),
        ("어린이제품 안전 특별법", ToolName.CHILDREN),
        ("수입식품안전관리 특별법", ToolName.FOOD_DRUG),
        ("식품위생법", ToolName.FOOD_DRUG),
        ("의료기기법", ToolName.FOOD_DRUG),
        ("체외진단의료기기법", ToolName.FOOD_DRUG),
        ("화장품법", ToolName.FOOD_DRUG),
        ("약사법", ToolName.FOOD_DRUG),
        ("위생용품 관리법", ToolName.FOOD_DRUG),
    )
}


def related_tool(law_name: str) -> ToolName | None:
    return RELATED_TOOLS.get(law_key(law_name))


def format_hs(code: str) -> str:
    """HS 숫자를 사람이 읽는 표기로 바꾼다. 10자리 "8516799000" → "8516.79-9000", 6자리 → "8516.79"."""
    if len(code) == 10:
        return f"{code[:4]}.{code[4:6]}-{code[6:]}"
    if len(code) == 6:
        return f"{code[:4]}.{code[4:]}"
    return code


def sale_actions(law_name: str, hs_codes: list[str], row: ConfirmationRow | None, documents: list[str],
                 agencies: list[str], omission: tuple[str, str] | None) -> list[str]:
    """요건 법령 하나에 대해 판매 방식별로 할 일. 판매 방식(구매대행/사입)은 사용자가 정한다.

    Args:
        omission: 고시 제7조 제2항의 생략 판단. ("excepted", 조건) = 생략 제외 법령, ("omittable", "") = 생략 가능,
            None = 고시를 확인하지 못함.
    """
    label = f"[「{law_name}」 · HS {', '.join(format_hs(code) for code in hs_codes)} 후보]"
    papers = ", ".join(documents) or (row.requirements if row is not None else "") or "해당 법령의 요건 확인 서류"
    who = f"{', '.join(agencies)}의 " if agencies else ""
    import_action = (f"{label} 사입·수입 판매: 이 HS로 분류되면 수입신고 때 세관장확인을 받아야 합니다. "
                     f"{who}{papers}를 미리 갖춰야 통관됩니다(관세법 제226조, 세관장확인 고시 별표 2).")
    if omission is None:
        return [import_action, f"{label} 구매대행: 개인 사용 목적 수입의 세관장확인 생략 여부는 확인이 필요합니다."]
    status, condition = omission
    if status == "excepted":
        note = f" 조건: {condition}" if condition else ""
        return [import_action,
                f"{label} 구매대행: 상행위 이외 목적 등 대외무역법 시행령 제19조 사유의 수입이어도 「{law_name}」 요건은 "
                f"세관장확인 생략 대상에서 빠집니다(세관장확인 고시 제7조 제2항 제1호 단서{note}). "
                "구매대행으로 들여와도 통관 때 요건 확인이 필요할 수 있습니다."]
    return [import_action,
            f"{label} 구매대행: 상행위 이외 목적 등 대외무역법 시행령 제19조 사유에 해당하는 수입이면 세관장확인을 "
            "생략할 수 있습니다(세관장확인 고시 제7조 제2항 제1호). 해당 여부는 확인이 필요합니다."]


def omission_status(law_name: str, exceptions: dict[str, str] | None) -> tuple[str, str] | None:
    """고시 제7조 제2항 제1호: 대외무역법 시행령 제19조 사유의 물품은 세관장확인을 생략할 수 있지만, 단서의 법령은 제외한다."""
    if exceptions is None:
        return None
    key = law_key(law_name)
    return ("excepted", exceptions[key]) if key in exceptions else ("omittable", "")
