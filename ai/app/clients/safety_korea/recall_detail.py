"""SafetyKorea 국내리콜 상세 클라이언트.

역할
    리콜 아이디 하나의 상세(위해 내용·사고 사례·조치 내용·첨부 이미지)를 조회.
"""

import httpx

from .base import SafetyKoreaBaseClient
from ...schemas.clients.safety_korea_request import RecallDetailRequest
from ...schemas.clients.safety_korea_response import RecallFile, RecallItem


class RecallDetailClient(SafetyKoreaBaseClient[RecallDetailRequest, RecallItem]):
    """국내리콜 상세(recallDetail) 클라이언트."""

    _ENDPOINT = "/openapi/api/recall/recallDetail.json"

    def _send(self, request: RecallDetailRequest) -> httpx.Response:
        """국내리콜 상세 조회를 요청한다.

        Args:
            request: 상세 조회 요청 (리콜 아이디).

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        return self._get_with_auth(self._ENDPOINT, params={
            "recallUid": request.recall_uid,             # 리콜 아이디
        })

    def _parse(self, raw: httpx.Response) -> RecallItem:
        """국내리콜 상세 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            RecallItem: 리콜정보 상세 (첨부파일 포함).
        """
        data = self._parse_result_data(raw) or {}
        if "recallFiles" in data and data["recallFiles"]:
            data["recallFiles"] = [
                RecallFile(**f) for f in data["recallFiles"]
            ]
        return RecallItem(**data)
