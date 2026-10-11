"""국립전파연구원 적합성평가 인증 유효여부 클라이언트.

역할
    전파 인증번호가 현재 유효한지(authYn) 조회.
    없는 번호도 authYn=N으로 오므로 resultCode(0001)로 "번호 없음"과 "무효"를 구분해야 함.
"""

import httpx

from .base import RadioBaseClient
from ...schemas.clients.radio_response import AuthStatusResponse


class RadioAuthStatusClient(RadioBaseClient[AuthStatusResponse]):
    """적합성평가 인증 유효여부 조회(getAuthStatus) 클라이언트."""

    _ENDPOINT = "/getAuthStatus.do"

    def _parse(self, raw: httpx.Response) -> AuthStatusResponse:
        """유효여부 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            AuthStatusResponse: authYn이 Y이면 유효, N이면 무효.
                resultCode가 0001이면 해당 번호 자체가 없음.
        """
        root = self._parse_xml(raw)
        return AuthStatusResponse(
            result_code=self._text(root, "resultCode") or "",
            result_msg=self._text(root, "resultMsg") or "",
            auth_yn=self._text(root, "authYn"),
        )
