"""SafetyKorea KC인증정보 검색 클라이언트.

역할
    인증번호·제품명·모델명 등으로 KC인증(전기용품·생활용품·어린이제품) 목록을 검색.
    상품의 KC인증 존재 여부와 인증 상태 확인에 사용.
"""

import httpx

from .base import SafetyKoreaBaseClient
from ...schemas.clients.safety_korea_request import CertSearchRequest
from ...schemas.clients.safety_korea_response import CertItem, CertSearchResponse


class CertSearchClient(SafetyKoreaBaseClient[CertSearchRequest, CertSearchResponse]):
    """KC인증정보 검색(certificationList) 클라이언트."""

    _ENDPOINT = "/openapi/api/cert/certificationList.json"

    def _send(self, request: CertSearchRequest) -> httpx.Response:
        """KC인증정보 검색을 요청한다.

        Args:
            request: 검색 요청. 사용 가능한 condition_key는 CertSearchRequest 참고.

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

    def _parse(self, raw: httpx.Response) -> CertSearchResponse:
        """KC인증정보 검색 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            CertSearchResponse: 인증정보 목록. certNum 조회는 인증번호가 요청과 일치하는 항목만 담음.
        """
        raw_items = self._parse_result_data(raw) or []
        # 필터가 무시된 응답의 첫 항목을 요청한 인증으로 믿으면 다른 제품의 인증 상태를 답하게 됨 (#185)
        condition_key = raw.request.url.params.get("conditionKey")
        if condition_key == "certNum":
            condition_value = raw.request.url.params.get("conditionValue")
            raw_items = [item for item in raw_items if item.get("certNum") == condition_value]
        return CertSearchResponse(
            items=[CertItem(**item) for item in raw_items],
        )
