"""SafetyKorea 국외리콜정보 검색 클라이언트.

역할
    제품명·브랜드·모델명 등으로 해외 기관이 발표한 리콜 목록을 검색.
    해외에서 들여오는 상품이 현지에서 리콜된 적 있는지 확인할 때 사용.
"""

import httpx

from .base import SafetyKoreaBaseClient
from ...schemas.clients.safety_korea_request import ForeignRecallSearchRequest
from ...schemas.clients.safety_korea_response import ForeignRecallItem, ForeignRecallSearchResponse


class ForeignRecallSearchClient(SafetyKoreaBaseClient[ForeignRecallSearchRequest, ForeignRecallSearchResponse]):
    """국외리콜정보 검색(fRecallList) 클라이언트."""

    _ENDPOINT = "/openapi/api/recall/fRecallList.json"

    def _send(self, request: ForeignRecallSearchRequest) -> httpx.Response:
        """국외리콜정보 검색을 요청한다.

        Args:
            request: 검색 요청. 사용 가능한 condition_key는 ForeignRecallSearchRequest 참고.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        return self._get_with_auth(self._ENDPOINT, params={
            "conditionKey": request.condition_key,       # 검색 구분
            "conditionValue": request.condition_value,   # 검색어
        })

    def _parse(self, raw: httpx.Response) -> ForeignRecallSearchResponse:
        """국외리콜정보 검색 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            ForeignRecallSearchResponse: 국외리콜 목록.
        """
        raw_items = self._parse_result_data(raw) or []
        return ForeignRecallSearchResponse(
            items=[ForeignRecallItem(**item) for item in raw_items],
        )
