"""SafetyKorea KC인증정보 상세 클라이언트.

역할
    KC 인증번호 하나의 상세(파생모델·공장·인증서 이미지·유사 인증 등)를 조회.
"""

import httpx

from .base import SafetyKoreaBaseClient
from ...schemas.clients.safety_korea_request import CertDetailRequest
from ...schemas.clients.safety_korea_response import CertItem


class CertDetailClient(SafetyKoreaBaseClient[CertDetailRequest, CertItem]):
    """KC인증정보 상세(certificationDetail) 클라이언트."""

    _ENDPOINT = "/openapi/api/cert/certificationDetail.json"

    def _send(self, request: CertDetailRequest) -> httpx.Response:
        """KC인증정보 상세 조회를 요청한다.

        Args:
            request: 상세 조회 요청 (인증번호).

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        return self._get_with_auth(self._ENDPOINT, params={
            "certNum": request.cert_num,                 # KC 인증번호
        })

    def _parse(self, raw: httpx.Response) -> CertItem:
        """KC인증정보 상세 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            CertItem: 인증정보 상세.
        """
        return CertItem(**(self._parse_result_data(raw) or {}))
