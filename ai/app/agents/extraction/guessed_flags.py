"""모델이 상품 종류로 짐작해 채운 false를 None(모름)으로 되돌리는 후처리.

추출 평가에서 치명 오답(정답은 모름인데 확정)의 대부분이 이런 false였다.
프롬프트·필드 설명으로 막아 보면 다른 칸까지 비워 두는 놓침이 함께 늘어서, 근거 기준이 분명한 칸만 코드에서 정리한다.
기준은 추출 프롬프트 원칙 1과 평가 정답표가 쓰는 "false의 근거"와 같다.
"""

from typing import Any

# 페이지가 "닿지 않는다"·"차단 기능이 없다"고 말할 때만 false인 칸. 그런 표기는 드물어서,
# 모델의 false는 상품 종류로 짐작한 값으로 보고 되돌린다 (정답표에도 이 칸의 false는 없음).
_GUESSED_FALSE_FIELDS = ("food_contact", "skin_contact", "wireless_shield")
# 발열 false의 근거는 전기를 쓰지 않는 상품이라는 점이다. 전기 상품인데 발열 언급이 없으면 모름이다.
_ELECTRIC_ONLY_FALSE_FIELDS = ("heating",)


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
