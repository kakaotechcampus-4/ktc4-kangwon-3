"""국립전파연구원 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel, Field


class RadioAuthRequest(BaseModel):
    """전파연구원 인증번호 조회 요청 (getAuthInfo, getAuthStatus 공통).

    Args:
        certification_number: 적합성평가 인증번호 (예: R-C-RTK-RTL8852BE).
            대소문자를 구분하므로 원문 그대로 넣음 (예: R-C-es5-ESP32C3WROOM02).
            빈 값·공백뿐인 값은 API가 0098을 정상 응답으로 돌려주므로 요청 전에 거부.
    """

    certification_number: str = Field(pattern=r"\S")
