"""국가기술표준원 제품안전정보센터 클라이언트 공통 베이스."""

from typing import Any

import httpx

from ..base import BaseClient, RequestT, ResponseT


class SafetyKoreaBaseClient(BaseClient[RequestT, ResponseT]):
    """국가기술표준원 제품안전정보센터(SafetyKorea) 클라이언트 공통 베이스.

    방식 : GET/JSON
    인증 : AuthKey 헤더 (safetykorea.kr 자체 발급).
    비고
        KC인증정보 조회/상세, 국내리콜 조회/상세, 국외리콜 조회 5개가 같은 인증·응답 형식을 씀.
        응답은 {resultCode, resultMsg, resultData}로 감싸져 옴.
        하위 클라이언트는 `_get_with_auth`로 요청하고 `_send`·`_parse`를 구현.
    """

    def __init__(self, auth_key: str):
        super().__init__(
            base_url="https://www.safetykorea.kr",
            timeout=30.0,
            headers={"AuthKey": auth_key},
        )

    def _get_with_auth(self, path: str, params: dict) -> httpx.Response:
        """AuthKey 헤더를 붙인 GET 요청을 보낸다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: 쿼리 파라미터.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        try:
            return self._get(path, params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                raise RuntimeError(
                    "SafetyKorea 인증 실패: AuthKey가 유효하지 않습니다 (302 Redirect)"
                ) from None
            raise

    def _parse_result_data(self, raw: httpx.Response) -> Any:
        """원문 응답에서 resultData를 꺼낸다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            Any: resultData 값. 목록 조회는 list, 상세 조회는 dict. 없으면 None.
        """
        return self._parse_json(raw).get("resultData")
