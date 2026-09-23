"""국립전파연구원 외부 API 응답 모델."""

from pydantic import BaseModel


class AuthInfoResponse(BaseModel):
    """인증정보 조회 응답 (getAuthInfo).

    Attributes:
        result_code: 결과코드. 0000=정상, 0001=없음, 0098=파라미터 오류.
        result_msg: 결과 메시지.
        bsm_nm: 신청자명.
        mtl_nm: 기자재명.
        matl_bsc_mdl_nm: 기본모델명.
        mtl_cef_no: 인증번호.
        matl_mfr_nm: 제조자명.
        dtl_inf_cd_nm: 제조국.
        cva_pcs_ymd: 인증일자.
        matl_etc_mtr: 비고.
    """

    result_code: str
    result_msg: str
    bsm_nm: str | None = None
    mtl_nm: str | None = None
    matl_bsc_mdl_nm: str | None = None
    mtl_cef_no: str | None = None
    matl_mfr_nm: str | None = None
    dtl_inf_cd_nm: str | None = None
    cva_pcs_ymd: str | None = None
    matl_etc_mtr: str | None = None


class AuthStatusResponse(BaseModel):
    """인증 유효여부 조회 응답 (getAuthStatus).

    Attributes:
        result_code: 결과코드. 0000=정상, 0001=없음.
        result_msg: 결과 메시지.
        auth_yn: 유효 여부. Y=유효, N=무효 또는 없음.
    """

    result_code: str
    result_msg: str
    auth_yn: str | None = None
