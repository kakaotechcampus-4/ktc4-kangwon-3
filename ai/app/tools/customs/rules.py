"""통관 Tool의 코드 규칙과 판매 안내 문구. LLM을 부르지 않는 순수 함수만 둔다.

- HS 표기: 숫자 10자리 → "8516.79-9000", 6자리 → "8516.79".
- 요건 법령과 다른 규제 Tool의 대응(검증 단계가 교차 확인할 수 있게 결과에 남긴다).
- 상품 신호가 아니라고 나오면 빼는 요건(HS 하나에 여러 물품이 묶여 일부 물품에만 걸리는 요건).
- 판매 방식별 안내(관세법 제226조, 고시 별표 2·제7조 제2항). HS가 후보이므로 모두 조건부로 쓴다.
  판매자가 읽는 문장이라 줄로 나누고 쉬운 말로 쓴다.
"""

import re

from ...schemas.product import Product
from ...schemas.schemas import ToolName
from ..common.questions import ANSWER_PREFIX
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


def requirement_subject(law_name: str) -> str:
    """요건 법령 하나에 대한 통관 판단의 제목. 종합 단계(related.py)가 이 제목으로 판단을 찾는다.

    Args:
        law_name: 요건 법령 이름.

    Returns:
        str: 판단 제목.
    """
    return f"세관장확인 대상 후보 — {law_name}"


def related_tool(law_name: str) -> ToolName | None:
    """요건 법령을 맡는 다른 규제 Tool을 찾는다.

    Args:
        law_name: 요건 법령 이름.

    Returns:
        ToolName | None: 관련 Tool. 없으면 None.
    """
    return RELATED_TOOLS.get(law_key(law_name))


# 요건 법령 → (상품 신호, 해당하는 물품). HS 하나에 여러 물품이 묶여 있어(예: 완구 HS에 모의총포) GW는 HS 단위로
# 요건을 주지만, 법은 그 물품에만 걸린다. 신호가 False(아니라고 추출)일 때만 빼고 None(모름)이면 남긴다.
PRODUCT_CONDITIONED_LAWS: dict[str, tuple[str, str]] = {
    law_key("총포·도검·화약류 등의 안전관리에 관한 법률"): ("weapon_like", "총포·도검·모의총포 등 무기 형태 물품"),
}


# 요건 법령 → (해당 물품 설명, 뺄 수 있는 소재 표기, 남겨야 하는 소재 표기). 소재 글에 '뺄 수 있는 표기'가 있고
# '남겨야 하는 표기'가 없을 때만 뺀다. 소재를 모르면 남기고, 종류를 모르는 가죽 표기가 같이 있어도 남긴다.
# 야생생물법 제2조·제16조: 수입허가 대상은 CITES 종과 그 가공품. 가축(소·양·돼지·염소) 가죽과 인조 가죽은 대상이 아님.
# 악어·뱀·도마뱀·타조·가오리·상어는 CITES 종이 섞여 있어 남긴다. "악어 무늬"처럼 무늬만 말해도 남긴다 (안전한 쪽).
# 송아지 가죽은 '카프스킨', 'calfskin'처럼 가죽을 붙인 표기만 본다. '카프'만 두면 '스카프', 'calf'만 두면
# 'mid-calf'(종아리)에서 걸려 소재를 모르는 상품의 요건이 빠진다 (리뷰 #708). 'calf leather'도 'wide calf leather boots'처럼
# 종아리 뜻으로 쓰여 넣지 않는다. 'fur'는 'Furla', 'furniture' 안에서 걸리지 않게 낱말로만 본다.
# 'PVC'도 'PVC 가죽'처럼 가죽을 붙인 표기만 본다. 'PVC'만 두면 '안감: PVC', 'PVC 무첨가'에서 걸린다 (리뷰 #708).
MATERIAL_CONDITIONED_LAWS: dict[str, tuple[str, re.Pattern[str], re.Pattern[str]]] = {
    law_key("야생생물 보호 및 관리에 관한 법률"): (
        "멸종위기종(CITES) 가죽이나 부위를 쓴 제품",
        re.compile(r"소가죽|소 가죽|우피|카우하이드|cow ?hide|cowskin|송아지 ?가죽|카프 ?(?:스킨|가죽|레더)|calf ?(?:skin|hide)|양가죽|양 가죽|램스킨|sheepskin|lambskin"
                   r"|돼지가죽|돼지 가죽|피그스킨|pigskin|염소가죽|고트스킨|goatskin|인조 ?가죽|합성 ?(?:가죽|피혁)|PU ?(?:가죽|레더|leather)"
                   r"|비건 ?(?:가죽|레더)|vegan leather|faux leather|PVC ?(?:가죽|레더|leather)", re.IGNORECASE),
        re.compile(r"악어|크로커다일|crocodile|앨리게이터|alligator|케이맨|caiman|뱀|파이톤|python|스네이크|snake|도마뱀|리자드|lizard"
                   r"|타조|ostrich|가오리|stingray|상어|shark|코끼리|elephant|상아|ivory|모피|(?<![A-Za-z])furs?(?![A-Za-z])", re.IGNORECASE),
    ),
}


# 종류를 밝히지 않은 가죽 표기. 뺄 수 있는 표기를 지우고도 이게 남으면 일부 소재만 확인된 상품으로 본다
_UNSPECIFIED_LEATHER = re.compile(r"가죽|피혁|레더|leather", re.IGNORECASE)
# 뺄 수 있는 표기 바로 뒤에 붙은 가죽 낱말 ('Cowhide Leather'의 Leather). 같은 소재를 가리켜 함께 지운다
_LEATHER_SUFFIX = re.compile(r" ?(?:가죽|레더|leather)", re.IGNORECASE)


def _without_excludable(text: str, excludable: re.Pattern[str]) -> str:
    """뺄 수 있는 소재 표기(와 바로 뒤의 가죽 낱말)를 지운 나머지 글.

    Args:
        text: 소재 글.
        excludable: 뺄 수 있는 소재 표기.

    Returns:
        str: 나머지 글.
    """
    parts: list[str] = []
    position = 0
    for match in excludable.finditer(text):
        parts.append(text[position:match.start()])
        position = match.end()
        suffix = _LEATHER_SUFFIX.match(text, position)
        if suffix is not None:
            position = suffix.end()
    parts.append(text[position:])
    return " ".join(parts)


def _unspecified_leather_left(material_texts: list[str], excludable: re.Pattern[str]) -> bool:
    """뺄 수 있는 소재 표기를 지우고도 종류를 밝히지 않은 가죽 표기가 남는지.

    판매자 답변 줄에 뺄 수 있는 소재가 있으면 답변 줄만 본다. 상품 이름·원문의 "가죽"은 답변이 종류를 밝힌 것으로 봄
    (리뷰 #774: "카메라 가죽 케이스"에 "소가죽"으로 답해도 이름의 "가죽"이 남아 요건이 빠지지 않던 것).
    남겨야 하는 소재(악어 등) 확인은 호출하는 쪽이 전체 글로 먼저 한다.

    Args:
        material_texts: 소재를 적은 글.
        excludable: 뺄 수 있는 소재 표기.

    Returns:
        bool: 종류를 모르는 가죽 표기가 남으면 True.
    """
    answers = [text for text in material_texts if text.startswith(ANSWER_PREFIX) and excludable.search(text)]
    text = " ".join(answers or material_texts)
    return bool(_UNSPECIFIED_LEATHER.search(_without_excludable(text, excludable)))


def material_question_helps(law_name: str, material_texts: list[str], material_known: bool) -> bool:
    """소재로 빠질 수 있는 요건이 남아 있을 때, 판매자에게 재질을 물으면 요건이 빠질 수 있는지.

    남겨야 하는 소재(악어 등)가 이미 확인됐으면 물어도 남으므로 False. 재질을 모르거나, 재질은 알지만 종류를
    밝히지 않은 가죽이 남아 있으면 True (예: 가죽 손잡이 → 소가죽이면 야생생물법 요건이 빠짐).

    Args:
        law_name: 남아 있는 요건 법령 이름 (excluded_by_product로 빠지지 않은 것).
        material_texts: 소재를 적은 글 (excluded_by_product와 같은 글).
        material_known: 통관 사실에 재질 조건이 있는지.

    Returns:
        bool: 재질 답으로 요건이 빠질 수 있으면 True. 소재 조건 법령이 아니면 False.
    """
    material = MATERIAL_CONDITIONED_LAWS.get(law_key(law_name))
    if material is None:
        return False
    _, excludable, keep = material
    text = " ".join(material_texts)
    if keep.search(text):
        return False
    if not material_known:
        return True
    return _unspecified_leather_left(material_texts, excludable)


def excluded_by_product(law_name: str, product: Product, material_texts: list[str] | None = None) -> str | None:
    """상품 신호나 소재 표기로 보아 이 요건 법령이 해당하지 않으면 그 이유를 돌려준다.

    Args:
        law_name: 요건 법령 이름.
        product: 상품 정보.
        material_texts: 소재를 적은 글(통관 사실의 material·composition, 상품 이름, 소재 줄). None이면 소재로 빼지 않음.

    Returns:
        str | None: 해당하는 물품 설명(뺄 때). 남길 요건이면 None.
    """
    key = law_key(law_name)
    condition = PRODUCT_CONDITIONED_LAWS.get(key)
    if condition is not None:
        signal, goods = condition
        return goods if getattr(product, signal) is False else None
    material = MATERIAL_CONDITIONED_LAWS.get(key)
    if material is None or not material_texts:
        return None
    goods, excludable, keep = material
    text = " ".join(material_texts)
    if not excludable.search(text) or keep.search(text):
        return None
    # 일부 소재만 확인된 상품은 빼지 않는다 (리뷰 #708: 안감은 인조 가죽인데 겉감 가죽의 종류는 모르는 경우).
    # 뺄 수 있는 표기를 지우고도 종류를 모르는 가죽 표기가 남으면 남긴다
    if _unspecified_leather_left(material_texts, excludable):
        return None
    return goods


def format_hs(code: str) -> str:
    """HS 숫자를 사람이 읽는 표기로 바꾼다. 10자리 "8516799000" → "8516.79-9000", 6자리 → "8516.79".

    Args:
        code: HS 숫자.

    Returns:
        str: 표기. 6·10자리가 아니면 그대로.
    """
    if len(code) == 10:
        return f"{code[:4]}.{code[4:6]}-{code[6:]}"
    if len(code) == 6:
        return f"{code[:4]}.{code[4:]}"
    return code


def sale_actions(law_name: str, hs_codes: list[str], row: ConfirmationRow | None, documents: list[str],
                 agencies: list[str], omission: tuple[str, str] | None) -> list[str]:
    """요건 법령 하나에 대한 할 일. 머리말, 할 일, 서류, 구매대행을 줄로 나눈 한 건으로 낸다.

    #640: 법령마다 200자 2문장이 나오던 것을 한 건으로 줄였고, 실사이트 화면(11/9 전동 클렌저)에서 여전히 읽기 어려워
    판매자가 읽는 말로 풀었다. '세관장확인'은 '세관에 서류를 내는 일'로, 조문 번호는 서류 줄에만 남긴다
    (전체 근거는 판단 카드의 근거에 있음). HS가 후보라 "내야 할 수 있습니다"로 쓴다.
    확인 기관 목록은 서류 이름에 발급처가 드러나 뺀다. 판매 방식(구매대행/사입)은 사용자가 정한다.

    Args:
        law_name: 요건 법령 이름.
        hs_codes: 이 법령이 걸린 HS.
        row: 고시 별표 2의 해당 행. 없으면 None.
        documents: GW가 준 요건 확인 서류.
        agencies: GW가 준 요건 확인 기관. 문장에는 쓰지 않음 (호출부 호환용).
        omission: 고시 제7조 제2항의 생략 판단. ("excepted", 조건) = 생략 제외 법령, ("omittable", "") = 생략 가능,
            None = 고시를 확인하지 못함.

    Returns:
        list[str]: 줄바꿈으로 나눈 할 일 한 건.
    """
    papers = ", ".join(documents) or (row.requirements if row is not None else "") or "해당 법령의 요건 확인 서류"
    lines = [
        f"[{law_name}] · 품목번호 HS {', '.join(format_hs(code) for code in hs_codes)} 후보",
        "수입 통관 때 세관에 아래 서류를 내야 할 수 있습니다.",
        f"- 미리 갖출 서류: {papers} (관세법 제226조, 세관장확인 고시 별표 2)",
        f"- {_agent_line(omission)}",
    ]
    note = law_note(law_name)
    if note:
        lines.append(f"- 참고: {note}")
    return ["\n".join(lines)]


def _agent_line(omission: tuple[str, str] | None) -> str:
    """구매대행으로 들여올 때도 서류가 필요한지 한 줄. 근거는 세관장확인 고시 제7조 제2항 제1호.

    Args:
        omission: omission_status 결과.

    Returns:
        str: 생략 제외 법령이면 "구매대행도 해당"(고시가 범위를 좁혔으면 그 조건을 덧붙임), 생략할 수 있는 법령이면
            생략될 수 있다는 안내, 고시를 읽지 못했으면 확인하지 못했다는 안내.
    """
    if omission is None:
        return "구매대행: 생략 여부를 확인하지 못함"
    kind, condition = omission
    if kind == "excepted":
        # 고시가 법령 뒤에 붙인 조건(예: 약사법은 오·남용우려 의약품에 한정). 빼면 범위를 넓혀 안내하게 됨
        scope = condition.strip().removeprefix("(").removesuffix(")").strip()
        return f"구매대행도 해당 (고시 조건: {scope})" if scope else "구매대행도 해당"
    # 고시 문구가 "생략할 수 있다"이고 대외무역법 시행령 제19조 사유는 수입 건마다 달라 확정하지 않음
    return "구매대행: 구매자 개인이 쓰려고 들여오는 경우 등에는 생략될 수 있음"


# 요건 법령 → HS 전체에 걸려 오지만 일부 물품에만 해당해 조건을 덧붙이는 설명 (#640).
# 야생생물법 제2조·제16조: 수입허가 대상은 CITES 종과 그 가공품. 가축인 소·양·돼지 가죽은 대상이 아님.
LAW_NOTES: dict[str, str] = {
    law_key("야생생물 보호 및 관리에 관한 법률"): ("악어·뱀 등 멸종위기종(CITES) 가죽이나 부위를 쓴 제품에만 해당하고, "
                                        "소가죽 등 일반 가축 가죽 제품은 해당하지 않습니다."),
}


def law_note(law_name: str) -> str | None:
    """요건 법령에 덧붙일 해당 조건 설명.

    Args:
        law_name: 요건 법령 이름.

    Returns:
        str | None: 설명. 없으면 None.
    """
    return LAW_NOTES.get(law_key(law_name))


def omission_status(law_name: str, exceptions: dict[str, str] | None) -> tuple[str, str] | None:
    """고시 제7조 제2항 제1호: 대외무역법 시행령 제19조 사유의 물품은 세관장확인을 생략할 수 있지만, 단서의 법령은 제외한다.

    Args:
        law_name: 요건 법령 이름.
        exceptions: 단서 법령 목록. 읽지 못했으면 None.

    Returns:
        tuple[str, str] | None: ("excepted", 조건) 또는 ("omittable", ""). 목록이 없으면 None.
    """
    if exceptions is None:
        return None
    key = law_key(law_name)
    return ("excepted", exceptions[key]) if key in exceptions else ("omittable", "")
