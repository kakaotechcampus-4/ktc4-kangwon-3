"""식약처 화장품 규제원료 클라이언트.

역할
    화장품 배합 금지·한도 원료와 국가별 규제 현황을 페이지 단위로 조회.
    검색 조건 없이 전체 목록을 주는 API라 DB 적재용으로 사용.
"""

import httpx

from .base import FdaBaseClient
from ...schemas.clients.fda_response import CosmeticsReglItem, CosmeticsReglResponse


class CosmeticsRegulationClient(FdaBaseClient[CosmeticsReglResponse]):
    """화장품 규제원료 조회 클라이언트."""

    _ENDPOINT = "/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService"

    def _parse(self, raw: httpx.Response) -> CosmeticsReglResponse:
        """화장품 규제원료 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            CosmeticsReglResponse: 규제 성분 목록.
        """
        body = self._parse_body(raw)
        raw_items = body.get("items", [])
        return CosmeticsReglResponse(
            total_count=body.get("totalCount", 0),
            items=[CosmeticsReglItem(**{k.lower(): v for k, v in item.items()}) for item in raw_items],
        )
