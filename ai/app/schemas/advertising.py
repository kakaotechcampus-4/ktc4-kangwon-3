"""표시·광고 Tool이 모델에게 받는 구조화 출력.

모델은 의심 문구를 원문 그대로 인용하고 유형만 고른다. 인용 대조, 위험도, 근거 조문, 할 일은 코드가 정한다.
"""

from enum import StrEnum

from pydantic import Field

from .base import StrictModel


# 「표시ㆍ광고 내용의 실증에 관한 운영 고시」 Ⅲ(실증자료 요청의 주요대상) 1~4호를 그대로 나눈 유형.
class AdvertisingRiskType(StrEnum):
    BODY_EFFECT = "body_effect"  # 1. 인체에 직접적으로 영향을 미친다는 내용
    SAFETY_CERTIFICATION = "safety_certification"  # 2. 안전 또는 환경, 신기술 (인증 표방 포함)
    PERFORMANCE_QUALITY = "performance_quality"  # 3. 성능, 효능, 품질
    RANKING_ABSOLUTE = "ranking_absolute"  # 4. 순위 표현, 지정고시 14 나 절대적 표현


class AdvertisingClaim(StrictModel):
    """판매자 문구에서 찾은 의심 문구 하나."""

    # listing_text에 있는 글자 그대로. 코드가 원문과 대조해 없으면 버린다.
    quote: str = Field(min_length=1)
    risk_type: AdvertisingRiskType
    reason: str = Field(min_length=1)


# 독스트링은 JSON 스키마 description으로 모델에 그대로 간다. "없으면 빈 목록"이라고 쓰면 빈 목록을
# 더 자주 냈다(얼굴 롤러 2회 모두 0개 → 중립 문장으로 바꾸자 2회 모두 3개). 빈 목록 허용은 프롬프트에만 둔다.
class AdvertisingReview(StrictModel):
    """판매자 문구에서 찾은 실증 필요 주장 목록."""

    claims: list[AdvertisingClaim]
