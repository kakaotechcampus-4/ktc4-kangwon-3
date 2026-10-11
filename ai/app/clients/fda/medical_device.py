"""식약처 의료기기 품목정보 클라이언트.

역할
    의료기기 품목(분류번호·등급·허가일·제조사·사용목적 등)을 페이지 단위로 조회.
    검색 조건 없이 전체 목록을 주는 API라 DB 적재용으로 사용.
"""

import httpx

from .base import FdaBaseClient
from ...schemas.clients.fda_response import MedicalDeviceItem, MedicalDeviceResponse


class MedicalDeviceClient(FdaBaseClient[MedicalDeviceResponse]):
    """의료기기 품목정보 조회 클라이언트. 응답이 items[].item 중첩 구조."""

    _ENDPOINT = "/1471000/MdeqPrdlstInfoService02/getMdeqPrdlstInfoInq02"

    def _parse(self, raw: httpx.Response) -> MedicalDeviceResponse:
        """의료기기 품목정보 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            MedicalDeviceResponse: 의료기기 품목 목록.
        """
        body = self._parse_body(raw)
        raw_items = body.get("items", [])
        # 의료기기는 items[].item 중첩 구조
        items = [
            MedicalDeviceItem(**{k.lower(): v for k, v in entry["item"].items()})
            for entry in raw_items
            if isinstance(entry, dict) and "item" in entry
        ]
        return MedicalDeviceResponse(
            total_count=body.get("totalCount", 0),
            items=items,
        )
