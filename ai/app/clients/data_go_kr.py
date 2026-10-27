"""공공데이터포털(data.go.kr) 클라이언트 공통 베이스."""

from urllib.parse import unquote

import httpx

from .request import RequestClient, RequestT, ResponseT


class DataGoKrClient(RequestClient[RequestT, ResponseT]):
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

    @staticmethod
    def _raise_for_result_code(result_code: str | None, result_message: str | None) -> None:
        """응답 header의 결과코드가 정상(00)이 아니면 예외를 올린다.

        data.go.kr은 요청 오류(예: numOfRows 초과)도 HTTP 200에 담아 빈 목록과 함께 돌려줌.
        그대로 넘기면 "0건"과 구분할 수 없으므로 수신 실패로 올림.

        Args:
            result_code: header의 resultCode. 없으면 None.
            result_message: header의 resultMsg. 없으면 None.

        Raises:
            RuntimeError: 결과코드가 00이 아니거나 header가 없는 경우.
        """
        if result_code == "00":
            return
        message = " ".join((result_message or "").split())    # 메시지 안 줄바꿈 정리
        raise RuntimeError(f"공공데이터포털 API 오류: resultCode={result_code} — {message}")
