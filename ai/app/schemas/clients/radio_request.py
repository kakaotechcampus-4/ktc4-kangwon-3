"""국립전파연구원 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel


class RadioAuthRequest(BaseModel):
    """전파연구원 인증번호 조회 요청 (getAuthInfo, getAuthStatus 공통).

    Args:
        mtl_cef_no: 적합성평가 인증번호 (예: KCC-REM-MJT-MJT).
    """

    mtl_cef_no: str
