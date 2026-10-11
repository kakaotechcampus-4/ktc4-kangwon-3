"""SafetyKorea 국내리콜정보 검색 클라이언트.

역할
    제품명·브랜드·모델명·인증번호 등으로 국내 리콜 목록을 검색.
    판매하려는 상품이 국내에서 리콜된 적 있는지 확인할 때 사용.
"""

import httpx

from .base import SafetyKoreaBaseClient
from ...schemas.clients.safety_korea_request import RecallSearchRequest
from ...schemas.clients.safety_korea_response import RecallItem, RecallSearchResponse


class RecallSearchClient(SafetyKoreaBaseClient[RecallSearchRequest, RecallSearchResponse]):
    """국내리콜정보 검색(recallList) 클라이언트."""

    _ENDPOINT = "/openapi/api/recall/recallList.json"

    def _send(self, request: RecallSearchRequest) -> httpx.Response:
        """국내리콜정보 검색을 요청한다.

        Args:
            request: 검색 요청. 사용 가능한 condition_key는 RecallSearchRequest 참고.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            ValueError: 공표일 검색값의 형식이 틀렸거나 최근 5년보다 오래된 경우.
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        self._check_recall_publish_date(request.condition_key, request.condition_value)
        return self._get_with_auth(self._ENDPOINT, params={
            "conditionKey": request.condition_key,       # 검색 구분
            "conditionValue": request.condition_value,   # 검색어
        })

    def _parse(self, raw: httpx.Response) -> RecallSearchResponse:
        """국내리콜정보 검색 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            RecallSearchResponse: 리콜정보 목록.
        """
        raw_items = self._parse_result_data(raw) or []
        return RecallSearchResponse(
            items=[RecallItem(**item) for item in raw_items],
        )
