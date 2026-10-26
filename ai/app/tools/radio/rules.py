"""전파 Tool의 코드 규칙과 판매 안내 문구. 모델을 부르지 않는 순수 함수만 둔다.

- 무선 기능 규칙: 상품 원문에 무선 기능 근거가 없으면 무선기기 후보를 내지 않는다.
- 주파수 정규화: 원문 주파수 표기를 MHz로 바꿔 후보 행의 대역과 함께 모델에 준다(대역으로 행을 빼지는 않는다).
- 판매 안내: 판매 목적 수입과 개인 사용 반입(시행령 별표 6의2)을 나눠 조건부로 쓴다.
"""

from ..common.facts import object_particle
from .evidence import Exemption, RadioItem, parse_bands

ASSESSMENT_PARAGRAPH = {"적합인증": "②", "적합등록": "③", "자기적합확인": "④"}


def normalized_bands(values: list[str]) -> list[tuple[float, float]]:
    """상품 원문의 주파수 표기들을 MHz 범위로. 읽을 수 없는 표기는 뺀다."""
    return list(dict.fromkeys(band for value in values for band in parse_bands(value)))


def band_label(band: tuple[float, float]) -> str:
    low, high = (f"{value:g}" for value in band)
    return f"{low} MHz" if low == high else f"{low}–{high} MHz"


def sale_actions(item: RadioItem, personal_use: Exemption | None) -> list[str]:
    """후보 행 기준으로 판매 전에 할 일. 판매 방식(구매대행/사입)은 사용자가 정한다."""
    kind = "·".join(item.assessment) or "적합성평가"
    label = f"[{item.name} · {kind} 후보]"
    actions = [f"{label} 사입·수입 판매: 이 기자재로 분류되면 판매 전 {kind}{object_particle(kind)} 받은 제품인지 "
               "KC 적합성평가 번호로 확인해야 합니다."]
    if personal_use is not None:
        actions.append(
            f"{label} 구매대행: 소비자가 개인 사용 목적으로 {personal_use.quantity} 반입하는 기자재는 적합성평가 "
            "면제 대상일 수 있습니다(전파법 시행령 별표 6의2, 반입일부터 1년 이내 판매 시 제외). "
            "구매대행이 이 면제에 해당하는지는 확인이 필요합니다.")
    return actions
