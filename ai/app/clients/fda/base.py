"""식약처 공공데이터 클라이언트 공통 베이스."""

from typing import ClassVar
from urllib.parse import unquote

import httpx

from ..base import BaseClient, ResponseT
from ...schemas.clients.fda_request import FdaPaginationRequest


class FdaBaseClient(BaseClient[FdaPaginationRequest, ResponseT]):
    """식약처(식품의약품안전처) 공공데이터 클라이언트 공통 베이스.

    방식 : GET/JSON
    서비스 키 : data.go.kr serviceKey 필요.
    비고
        의료기기 품목정보, 화장품 규제원료가 같은 요청 형식(페이지 번호·건수)을 씀.
        하위 클라이언트는 `_ENDPOINT`와 `_parse`만 구현.
        serviceKey는 URL 인코딩된 상태로 받아 디코딩 후 httpx params로 넘김 (이중 인코딩 방지).
    """

    _ENDPOINT: ClassVar[str]

    def __init__(self, service_key: str):
        super().__init__(base_url="https://apis.data.go.kr")
        self._service_key = unquote(service_key)

    def _send(self, request: FdaPaginationRequest) -> httpx.Response:
        """페이지 번호·건수로 조회를 요청한다.

        Args:
            request: 페이지 조회 요청 파라미터.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 서비스 키는 마스킹됨.
        """
        try:
            return self._get(self._ENDPOINT, params={
                "serviceKey": self._service_key,            # 서비스 키
                "type": "json",                             # 응답 포맷
                "pageNo": str(request.page),                # 페이지 번호
                "numOfRows": str(request.num_of_rows),      # 페이지당 건수
            })
        except httpx.HTTPStatusError as e:
            raise self._mask_url(e) from None

    def _parse_body(self, raw: httpx.Response) -> dict:
        """원문 응답에서 body를 꺼낸다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            dict: 응답 body (pageNo, totalCount, numOfRows, items 포함). 없으면 빈 dict.
        """
        return self._parse_json(raw).get("body", {})
