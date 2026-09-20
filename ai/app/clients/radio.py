"""국립전파연구원 적합성평가 외부 API 클라이언트."""

from xml.etree.ElementTree import Element

from .base import BaseClient
from ..schemas.clients.radio_request import RadioAuthRequest
from ..schemas.clients.radio_response import AuthInfoResponse, AuthStatusResponse

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)


class RadioClient(BaseClient):
    """국립전파연구원(emsit) 적합성평가 클라이언트.

    방식 : GET/XML
    서비스 키 : 불필요. 단, 브라우저 User-Agent 헤더 필수.
    비고
        인증정보 조회(getAuthInfo)와 유효여부 조회(getAuthStatus) 2개
        엔드포인트를 제공한다. 없는 번호도 HTTP 200이며
        resultCode로 판별해야 한다.
    """

    _AUTH_INFO_ENDPOINT = "/getAuthInfo.do"
    _AUTH_STATUS_ENDPOINT = "/getAuthStatus.do"

    def __init__(self):
        super().__init__(
            base_url="http://emsit.go.kr/openapi/service/AuthenticationInfoService",
            headers={"User-Agent": _BROWSER_UA},
        )

    def get_auth_info(self, request: RadioAuthRequest) -> AuthInfoResponse:
        """인증번호로 인증정보를 조회한다.

        Args:
            request: 인증번호 조회 요청.

        Returns:
            AuthInfoResponse: 기자재명, 모델명, 신청자, 제조국 등.
                resultCode가 0001이면 조회 결과 없음.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        response = self._get(self._AUTH_INFO_ENDPOINT, params={
            "mtlCefNo": request.mtl_cef_no,
        })
        root = self._parse_xml(response)
        return AuthInfoResponse(
            result_code=self._text(root, "resultCode") or "",
            result_msg=self._text(root, "resultMsg") or "",
            bsm_nm=self._text(root, "bsmNm"),
            mtl_nm=self._text(root, "mtlNm"),
            matl_bsc_mdl_nm=self._text(root, "matlBscMdlNm"),
            mtl_cef_no=self._text(root, "mtlCefNo"),
            matl_mfr_nm=self._text(root, "matlMfrNm"),
            dtl_inf_cd_nm=self._text(root, "dtlInfCdNm"),
            cva_pcs_ymd=self._text(root, "cvaPcsYmd"),
            matl_etc_mtr=self._text(root, "matlEtcMtr"),
        )

    def get_auth_status(self, request: RadioAuthRequest) -> AuthStatusResponse:
        """인증번호의 유효 여부를 조회한다.

        Args:
            request: 인증번호 조회 요청.

        Returns:
            AuthStatusResponse: authYn이 Y이면 유효, N이면 무효.
                resultCode가 0001이면 해당 번호 자체가 없음.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        response = self._get(self._AUTH_STATUS_ENDPOINT, params={
            "mtlCefNo": request.mtl_cef_no,
        })
        root = self._parse_xml(response)
        return AuthStatusResponse(
            result_code=self._text(root, "resultCode") or "",
            result_msg=self._text(root, "resultMsg") or "",
            auth_yn=self._text(root, "authYn"),
        )

    @staticmethod
    def _text(element: Element, tag: str) -> str | None:
        """XML 엘리먼트에서 태그의 텍스트를 꺼낸다.

        Args:
            element: 부모 엘리먼트.
            tag: 찾을 태그명.

        Returns:
            str | None: 태그 텍스트. 없으면 None.
        """
        child = element.find(tag)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
        return None
