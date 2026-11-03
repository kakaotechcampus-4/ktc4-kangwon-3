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
        # 충전 단자·케이블이 적혀 있으면 유선 충전 제품으로 보고 무선충전 없음을 인정 (정답표 기준)
        re.compile(
            r"USB ?충전|Type-?C|타입 ?C|충전 ?(?:케이블|단자|포트|어댑터)|charging (?:port|cable)|micro ?usb|usb charging"
            r"|유선 ?충전|자기 충전",
            re.IGNORECASE,
        ),
    ),
}
# 식물성이 아닌 재질 표기. 이 중 하나가 원문에 있어야 plant_material=false를 인정한다.
# 재질 표기가 없는 페이지의 false는 사진이나 상품 종류로 짐작한 값이다 (프롬프트 "재질 표기가 없으면 None").
_NON_PLANT_MATERIAL = re.compile(
    r"플라스틱|ABS|PP\b|PC\b|PE\b|PET|TPU|PVC|실리콘|실리카겔|스테인리스|스틸|금속|알루미늄|합금|유리|세라믹|도자기"
    r"|나일론|폴리|스판덱스|아크릴|합성|고무|SBR|가죽|레진|수지"
    r"|metal|steel|alumin|plastic|silicone|glass|ceramic|nylon|polyester|rubber|leather|resin|iron|stainless|acrylic",
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
