"""모델이 상품 종류로 짐작해 채운 false를 None(모름)으로 되돌리는 후처리.

추출 평가에서 치명 오답(정답은 모름인데 확정)의 대부분이 이런 false였다.
프롬프트·필드 설명으로 막아 보면 다른 칸까지 비워 두는 놓침이 함께 늘어서, 근거 기준이 분명한 칸만 코드에서 정리한다.
기준은 추출 프롬프트 원칙 1과 평가 정답표가 쓰는 "false의 근거"와 같다.

세 가지를 되돌린다.
    - drop_guessed_false: 페이지가 부정을 말하는 일이 거의 없는 칸. 원문을 보지 않고 false를 전부 되돌림
    - drop_unsupported_false: 페이지가 부정을 말할 수 있는 칸. 원문에 그 표기가 없을 때만 되돌림
    - drop_conflicted_battery: 코드 규칙이 배터리 모순을 찾은 페이지. 배터리 칸의 확정(true·false)을 되돌림
"""

import re
from typing import Any

# 페이지가 "닿지 않는다"·"차단 기능이 없다"고 말할 때만 false인 칸. 그런 표기는 드물어서,
# 모델의 false는 상품 종류로 짐작한 값으로 보고 되돌린다 (정답표에도 이 칸의 false는 없음).
_GUESSED_FALSE_FIELDS = ("food_contact", "skin_contact", "wireless_shield")
# 발열 false의 근거는 전기를 쓰지 않는 상품이라는 점이다. 전기 상품인데 발열 언급이 없으면 모름이다.
_ELECTRIC_ONLY_FALSE_FIELDS = ("heating",)

# 스펙표의 예/아니오 항목이나 "없음" 표기에서 "아니요" 쪽 답
_NO = r"\s*[:：]?\s*\n?\s*(?:no|아니요|아니오|없음|없다|N)\b"
# 전기 상품(또는 전기 여부를 모르는 상품)에서 false를 짐작이 아니라고 볼 수 있는 페이지 표기.
# 전기 상품은 배터리·무선 기능이 있을 수 있어, 언급이 없다는 것만으로는 없다고 확정할 수 없다 (정답표 기준).
# 전기를 쓰지 않는 상품은 재질·형태가 근거라 그대로 둔다.
_NEGATIVE_EVIDENCE: dict[str, tuple[re.Pattern[str], ...]] = {
    "battery_included": (
        re.compile(r"배터리가? 포함되어 있습니까\??" + _NO, re.IGNORECASE),
        re.compile(r"(?:배터리|전지)가? ?(?:없는|없음|미포함|불포함)", re.IGNORECASE),
        # 코드로 콘센트에 꽂아 쓰는 제품. 전원 사양이 페이지에 있으면 전지 없음을 인정 (정답표 기준)
        re.compile(r"전원 ?코드|코드 ?길이|길이의 코드|콘센트", re.IGNORECASE),
    ),
    "wireless_comm": (
        re.compile(r"스마트 기기인가요\??" + _NO, re.IGNORECASE),
        re.compile(r"(?:블루투스|와이파이|WiFi|무선 ?(?:통신|연결))\s*[:：]?\s*(?:없음|미지원|no)\b", re.IGNORECASE),
    ),
    "wireless_charging": (
        re.compile(r"무선 ?충전\s*[:：]?\s*(?:없음|미지원|no|아니요)\b", re.IGNORECASE),
        # 충전 단자·케이블이 적혀 있으면 유선 충전 제품으로 보고 무선충전 없음을 인정.
        # 정답표 기준은 "충전 단자·충전 케이블·자기 충전"(골전도 이어폰)까지. USB 충전·Type-C 등은 같은 뜻으로 넓힌 것
        # (정답표에서 "USB 충전"만 있는 상품은 무선충전 None)
        re.compile(
            r"USB ?충전|Type-?C|타입 ?C|충전 ?(?:케이블|단자|포트|어댑터)|charging (?:port|cable)|micro ?usb|usb charging"
            r"|유선 ?충전|자기 충전",
            re.IGNORECASE,
        ),
    ),
}
# 식물성이 아닌 재질 표기. 이 중 하나가 원문에 있어야 plant_material=false를 인정한다.
# 재질 표기가 없는 페이지의 false는 사진이나 상품 종류로 짐작한 값이다 (프롬프트 "재질 표기가 없으면 None").
# 영문 약어는 다른 단어 안(CPC의 PC, Type의 pe, App의 pp)에서 안 잡히게 앞뒤를 막고, "PP소재"처럼 한글이 붙은 표기는 잡음.
# "합성"은 재질 이름으로만 (적합성평가 제외)
_NON_PLANT_MATERIAL = re.compile(
    r"플라스틱|(?<![A-Za-z0-9])(?:ABS|PP|PC|PE|PET|TPU|PVC|SBR)(?![A-Za-z])|실리콘|실리카겔|스테인리스|스틸|금속|알루미늄|합금"
    r"|유리|세라믹|도자기|나일론|폴리|스판덱스|아크릴|합성(?:수지|섬유|피혁|가죽|고무)|고무|가죽|레진|수지"
    r"|metal|steel|alumin|plastic|silicone|glass|ceramic|nylon|polyester|rubber|leather|resin"
    r"|(?<![A-Za-z])iron(?![A-Za-z])|stainless|acrylic",
    re.IGNORECASE,
)
# 코드 규칙이 배터리 모순(용량 표기 + "배터리 미포함")을 찾았을 때 확정하지 않는 칸 (원칙 5)
_BATTERY_FIELDS = ("battery_included", "battery_is_the_product")


def drop_guessed_false(attributes: dict[str, Any]) -> list[str]:
    """근거 없이 채운 false를 None으로 바꾼다. attributes를 그 자리에서 고친다.

    Args:
        attributes: 모델이 채운 상품 특성 (ProductAttributes.model_dump()).

    Returns:
        list[str]: None으로 바꾼 필드 이름.
    """
    dropped = [name for name in _GUESSED_FALSE_FIELDS if attributes.get(name) is False]
    if attributes.get("electrical_powered") is not False:
        dropped += [name for name in _ELECTRIC_ONLY_FALSE_FIELDS if attributes.get(name) is False]
    attributes.update(dict.fromkeys(dropped))
    return dropped


def drop_unsupported_false(attributes: dict[str, Any], text: str) -> list[str]:
    """원문에 부정 표기가 없는 false를 None으로 바꾼다. attributes를 그 자리에서 고친다.

    전기 상품(또는 모름)의 배터리·무선 통신·무선충전 false는 "배터리가 포함되어 있습니까? 아니요"·"전원 코드"·
    "충전 단자" 같은 표기가 있을 때만, plant_material false는 식물성이 아닌 재질 표기가 있을 때만 남긴다.
    이미지만 있는 입력은 글 근거가 없어 이 칸의 false가 전부 None이 된다 (사진으로 짐작한 false를 믿지 않음).

    Args:
        attributes: 모델이 채운 상품 특성 (ProductAttributes.model_dump()).
        text: 모델이 읽은 판매자 영역 원문. 블록을 합친 글.

    Returns:
        list[str]: None으로 바꾼 필드 이름.
    """
    dropped: list[str] = []
    if attributes.get("electrical_powered") is not False:
        dropped += [
            name for name, patterns in _NEGATIVE_EVIDENCE.items()
            if attributes.get(name) is False and not any(pattern.search(text) for pattern in patterns)
        ]
    if attributes.get("plant_material") is False and not _NON_PLANT_MATERIAL.search(text):
        dropped.append("plant_material")
    attributes.update(dict.fromkeys(dropped))
    return dropped


# 소재·재질·재료·성분 줄("키\n값" 또는 "키: 값")의 값에 식물성 재질이 적혀 있으면 plant_material을 확정한다.
# 모델이 "72% Cotton"·"소재: 종이"를 false로 두는 일이 잦다(초안 50건 측정, 2026-11-05).
# 재질 줄 밖의 낱말(포장 "종이 상자", "나무 심기 프로그램")은 근거가 아니라 줄 단위로만 본다.
_MATERIAL_ROW = re.compile(
    r"(?:^|\n)[^\n:：]{0,20}(?:소재|재질|재료|성분|material)[^\n:：]{0,10}[:：]?[ \t]*\n?[ \t]*(?P<value>[^\n]+)",
    re.IGNORECASE,
)
# "면"은 "양면발열"·"면도기"처럼 다른 낱말 안에도 있어 한글 낱말 안의 면은 재질로 보지 않는다.
_PLANT_MATERIAL = re.compile(
    r"(?<![가-힣])면(?![가-힣])|cotton|코튼|종이|paper|나무|목재|원목|wood|우드|대나무|bamboo|라탄|등나무|rattan"
    r"|린넨|리넨|linen|황마|jute|코르크|cork|밀짚|짚|straw|티크|teak|월넛|walnut|오크|oak|소나무|pine",
    re.IGNORECASE,
)


def drop_contradicted_plant_false(attributes: dict[str, Any], text: str) -> tuple[list[str], list[str]]:
    """소재 줄에 식물성 재질이 있는데 plant_material이 False면 None으로 되돌리고 모순 문장을 만든다.

    코드는 식물성 여부를 대신 정하지 않는다(True로 확정하지 않음). 페이지 표기와 모델의 False가 어긋나는
    명확한 경우만 '애매함'으로 돌려 판단 단계로 넘긴다. attributes를 그 자리에서 고친다.

    Args:
        attributes: 모델이 채운 상품 특성 (ProductAttributes.model_dump()).
        text: 모델이 읽은 판매자 영역 원문. 블록을 합친 글.

    Returns:
        tuple[list[str], list[str]]: None으로 바꾼 필드 이름, conflicts에 넣을 문장.
    """
    if attributes.get("plant_material") is not False:
        return [], []
    for row in _MATERIAL_ROW.finditer(text):
        value = row.group("value").strip()
        if _PLANT_MATERIAL.search(value):
            attributes["plant_material"] = None
            return ["plant_material"], [f'소재 표기 "{value}"에 식물성 재질이 있어 확인이 필요합니다.']
    return [], []


# 판매자 글의 효능·미용 표방 문구. 프롬프트는 "상품 이름 안에 있어도 표방"이라고 하지만 모델(gpt-4.1-mini)이
# 제목의 '스트레스 완화'·'치아 미백 효과'를 false로 두는 일이 잦다(초안 50건 측정, 2026-11-05). 표현이 분명한 것만 잡는다.
# 부정("통증 없는 이어폰")은 "완화·개선" 같은 효능 동사를 요구해 걸리지 않게 하고, 촉감 설명(skin-friendly)은 넣지 않는다.
# 영어는 낱말 경계로 막는다("Singapore"의 pore, "uplifting"의 lifting). 한국어 "피로"는 "팔의 피로를 줄여" 같은
# 인체공학 설명에도 쓰여 "피로 회복"만, "교정기"는 쇼핑몰 분류 "교정기 및 지지대"에도 있어 "자세·등·체형 교정"만 본다.
_KO_RELIEF = r"(?:완화|경감|해소|개선|감소|줄여)"
_MEDICAL_CLAIM = re.compile(
    r"(?:통증|스트레스|가려움|두통|염증|부종|불면|근육통|관절통|생리통)\s*(?:을|를)?\s*" + _KO_RELIEF
    + r"|피로\s*회복|혈액\s*순환|관절\s*(?:을|를)?\s*(?:안정|보호|지지)|근육\s*이완|경락"
    + r"|(?:자세|등|체형|척추|굽은\s*등)\s*(?:을|를)?\s*교정"
    + r"|(?:여드름|무좀|습진|탈모|비염|불면증)\s*(?:치료|개선|완화)"
    + r"|지방\s*(?:연소|분해|감소)|체중\s*감소|슬리밍|셀룰라이트|수면\s*(?:개선|질)|면역|혈압|혈당|당뇨"
    + r"|\b(?:(?:pain|stress|itch|headache|sunburn|inflammation)\s*(?:relief|reliev\w*|improve\w*)"
    + r"|headache\s*reli[ef]\w*|blood\s*circulation|circulation\s*improve\w*|fat\s*(?:loss|burn\w*)|weight\s*loss"
    + r"|slimming|sleep\s*quality|posture\s*correct\w*)\b",
    re.IGNORECASE,
)
_COSMETIC_CLAIM = re.compile(
    r"미백|주름\s*(?:개선|완화|제거)|리프팅|탄력\s*(?:강화|개선|회복)"
    + r"|모공\s*(?:클리너|축소|케어|청소|관리)|블랙헤드|각질\s*(?:제거|케어|관리)"
    + r"|피부\s*(?:톤|결|재생|탄력|미백|보습|광채)|피부톤|붓기\s*(?:완화|제거|감소|빼)"
    + r"|(?:머릿결|모발|헤어)\s*(?:윤기|보호|케어|손상\s*개선)|윤기\s*있고|건강한\s*모발"
    + r"|\b(?:whitening|wrinkles?|lifting|elasticity|pores?|blackheads?|exfoliat\w*|puffiness|frizz"
    + r"|skin\s*(?:tone|brighten\w*|rejuvenat\w*)|smooth\s*hair|hair\s*care)\b",
    re.IGNORECASE,
)


def drop_contradicted_claim_false(attributes: dict[str, Any], text: str) -> tuple[list[str], list[str]]:
    """효능·미용 표방 문구가 있는데 medical_claim·cosmetic_claim이 False면 None으로 되돌리고 모순 문장을 만든다.

    코드는 표방 여부를 대신 정하지 않는다(True로 확정하지 않음). 표방은 해석이 갈리는 칸이라, 페이지 문구와
    모델의 False가 어긋나는 명확한 경우만 '애매함'으로 돌려 판단 단계로 넘긴다. attributes를 그 자리에서 고친다.

    Args:
        attributes: 모델이 채운 상품 특성 (ProductAttributes.model_dump()).
        text: 모델이 읽은 판매자 제목과 판매자 영역 원문. 합친 글.

    Returns:
        tuple[list[str], list[str]]: None으로 바꾼 필드 이름, conflicts에 넣을 문장.
    """
    dropped: list[str] = []
    conflicts: list[str] = []
    for name, pattern, kind in (
        ("medical_claim", _MEDICAL_CLAIM, "효능 표방"),
        ("cosmetic_claim", _COSMETIC_CLAIM, "미용 효과 표방"),
    ):
        if attributes.get(name) is not False:
            continue
        match = pattern.search(text)
        if match:
            attributes[name] = None
            dropped.append(name)
            sentence = f'판매자 문구 "{match.group(0).strip()}"가 {kind}일 수 있어 확인이 필요합니다.'
            if sentence not in conflicts:
                conflicts.append(sentence)
    return dropped, conflicts


def drop_conflicted_battery(attributes: dict[str, Any]) -> list[str]:
    """배터리 모순이 있는 페이지에서 배터리 두 칸의 확정을 None으로 바꾼다. attributes를 그 자리에서 고친다.

    원칙 5(모순이면 확정하지 않음)를 코드가 보장한다. 모델은 모순을 conflicts에 적으면서도 한쪽을 골라
    확정하는 일이 있어서다. 호출자가 코드 규칙(detect_battery_capacity_conflict)으로 모순을 찾았을 때만 부른다.

    Args:
        attributes: 모델이 채운 상품 특성 (ProductAttributes.model_dump()).

    Returns:
        list[str]: None으로 바꾼 필드 이름.
    """
    dropped = [name for name in _BATTERY_FIELDS if attributes.get(name) is not None]
    attributes.update(dict.fromkeys(dropped))
    return dropped
