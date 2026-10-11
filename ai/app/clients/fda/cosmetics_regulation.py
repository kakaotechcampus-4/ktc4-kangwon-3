"""식약처 화장품 규제원료 클라이언트.

역할
    화장품 배합 금지·한도 원료와 국가별 규제 현황을 페이지 단위로 조회.
    검색 조건 없이 전체 목록을 주는 API라 DB 적재용으로 사용.
"""

import httpx

from .base import FdaBaseClient
from ...schemas.clients.fda_response import CosmeticsRegulationItem, CosmeticsRegulationResponse


class CosmeticsRegulationClient(FdaBaseClient[CosmeticsRegulationResponse]):
    """화장품 규제원료 조회 클라이언트."""

    _ENDPOINT = "/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService"

    def _parse(self, raw: httpx.Response) -> CosmeticsRegulationResponse:
        """화장품 규제원료 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            CosmeticsRegulationResponse: 규제 성분 목록.
        """
        body = self._parse_body(raw)
        raw_items = body.get("items", [])
        return CosmeticsRegulationResponse(
            total_count=body.get("totalCount", 0),
            items=[self._parse_item(item) for item in raw_items],
        )

    def _parse_item(self, item: dict) -> CosmeticsRegulationItem:
        """화장품 규제원료 원문 항목 하나를 스키마로 변환한다.

        Args:
            item: 원문 items 항목.

        Returns:
            CosmeticsRegulationItem: 풀어 쓴 필드 이름으로 옮긴 항목.
        """
        return CosmeticsRegulationItem(
            ingredient_name=item.get("INGR_STD_NAME"),                  # 원료 표준명
            ingredient_english_name=item.get("INGR_ENG_NAME"),          # 원료 영문명
            prohibited_countries=self._split_countries(item.get("PROH_NATIONAL")),     # 사용 금지 국가
            restricted_countries=self._split_countries(item.get("LIMIT_NATIONAL")),    # 사용 한도 국가
        )

    @staticmethod
    def _split_countries(text: str | None) -> list[str]:
        """쉼표로 이어진 국가 문자열을 목록으로 나눈다.

        Args:
            text: 원문 국가 문자열 (예: "EU,대만,아세안"). 해당 국가가 없으면 null로 옴.

        Returns:
            list[str]: 국가 목록. 없으면 빈 목록.
        """
        if not text:
            return []
        return [country.strip() for country in text.split(",") if country.strip()]
