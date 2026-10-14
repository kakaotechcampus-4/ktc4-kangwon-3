"""국립전파연구원 적합성평가 인증정보 클라이언트.

역할
    전파 인증번호로 기자재명·모델명·신청자·제조자·제조국·인증일자를 조회.
    인증이 실제로 이 제품의 것인지 대조할 때 사용.
"""

import httpx

from .base import RadioBaseClient
from ...schemas.clients.radio_response import AuthInfoResponse


class RadioAuthInfoClient(RadioBaseClient[AuthInfoResponse]):
    """적합성평가 인증정보 조회(getAuthInfo) 클라이언트."""

    _ENDPOINT = "/getAuthInfo.do"

    def _parse(self, raw: httpx.Response) -> AuthInfoResponse:
        """인증정보 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            AuthInfoResponse: 기자재명, 모델명, 신청자, 제조국 등.
                resultCode가 0001이면 조회 결과 없음.
        """
        root = self._parse_xml(raw)
        return AuthInfoResponse(
            result_code=self._text(root, "resultCode") or "",
            result_message=self._text(root, "resultMsg") or "",
            applicant_name=self._text(root, "bsmNm"),
            equipment_name=self._text(root, "mtlNm"),
            model_name=self._text(root, "matlBscMdlNm"),
            certification_number=self._text(root, "mtlCefNo"),
            manufacturer_name=self._text(root, "matlMfrNm"),
            manufacture_country=self._text(root, "dtlInfCdNm"),
            certified_date=self._text(root, "cvaPcsYmd"),
            remarks=self._text(root, "matlEtcMtr"),
        )
