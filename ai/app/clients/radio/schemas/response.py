"""국립전파연구원 외부 API 응답 모델."""

from pydantic import BaseModel


class AuthInfoResponse(BaseModel):
    """인증정보 조회 응답 (getAuthInfo).

    Attributes:
        result_code: 결과코드. 0000=정상, 0001=없음, 0098=파라미터 오류.
        result_message: 결과 메시지.
        applicant_name: 신청자(인증받은 업체)명.
        equipment_name: 기자재명.
        model_name: 기본모델명.
        certification_number: 인증번호.
        manufacturer_name: 제조자명.
        manufacture_country: 제조국.
        certified_date: 인증일자 (YYYY-MM-DD).
        remarks: 비고.
    """

    result_code: str
    result_message: str
    applicant_name: str | None = None
    equipment_name: str | None = None
    model_name: str | None = None
    certification_number: str | None = None
    manufacturer_name: str | None = None
    manufacture_country: str | None = None
    certified_date: str | None = None
    remarks: str | None = None


class AuthStatusResponse(BaseModel):
    """인증 유효여부 조회 응답 (getAuthStatus).

    Attributes:
        result_code: 결과코드. 0000=정상, 0001=없음.
        result_message: 결과 메시지.
        auth_status: 유효 여부. Y=유효, N=무효 또는 없음.
    """

    result_code: str
    result_message: str
    auth_status: str | None = None
