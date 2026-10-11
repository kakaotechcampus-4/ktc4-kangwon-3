"""공공데이터포털(data.go.kr) 클라이언트 공통 베이스."""

from urllib.parse import unquote

import httpx

from .base import BaseClient, RequestT, ResponseT


class DataGoKrClient(BaseClient[RequestT, ResponseT]):
    """공공데이터포털(apis.data.go.kr) API 공통 베이스.

    서비스 키 : data.go.kr serviceKey 필요.
    비고
        serviceKey는 URL 인코딩된 상태로 받아 디코딩 후 httpx params로 넘김 (이중 인코딩 방지).
        하위 클라이언트는 `_get_with_service_key`로 요청하고 `_send`·`_parse`를 구현.

    Args:
        service_key: data.go.kr 발급 서비스 키 (URL 인코딩된 값).
        timeout: 요청 제한 시간(초). 기본 10초.
    """

    def __init__(self, service_key: str, timeout: float = 10.0):
        super().__init__(base_url="https://apis.data.go.kr", timeout=timeout)
        self._service_key = unquote(service_key)

    def _get_with_service_key(self, path: str, params: dict) -> httpx.Response:
        """서비스 키를 붙여 GET 요청을 보낸다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: 서비스 키를 뺀 쿼리 파라미터.

        Returns:
            httpx.Response: 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 서비스 키는 마스킹됨.
        """
        try:
            return self._get(path, params={"serviceKey": self._service_key, **params})
        except httpx.HTTPStatusError as e:
            raise self._mask_url(e) from None
