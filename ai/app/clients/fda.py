"""식약처 소관 외부 API 클라이언트."""

from urllib.parse import unquote

import httpx

from .base import BaseClient
from ..schemas.clients.fda_request import (
    CosmeticsReglRequest,
    MedicalDeviceRequest,
)
from ..schemas.clients.fda_response import (
    CosmeticsReglItem,
    CosmeticsReglResponse,
    MedicalDeviceItem,
    MedicalDeviceResponse,
)


class FdaClient(BaseClient):
    """식약처(식품의약품안전처) 공공데이터 클라이언트.

    방식 : GET/JSON
    서비스 키 : data.go.kr serviceKey 필요.
    비고
        의료기기 품목정보, 화장품 규제원료 2개 엔드포인트 제공.
        의료기기 응답만 items[].item 중첩 구조.
    """

    _MEDICAL_DEVICE_ENDPOINT = "/1471000/MdeqPrdlstInfoService02/getMdeqPrdlstInfoInq02"
    _COSMETICS_REGL_ENDPOINT = "/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService"

    def __init__(self, service_key: str):
        super().__init__(base_url="https://apis.data.go.kr")
        self._service_key = unquote(service_key)

    # -- 의료기기 --

    def get_medical_devices(self, request: MedicalDeviceRequest) -> MedicalDeviceResponse:
        """의료기기 품목정보를 조회한다.

        Args:
            request: 조회 요청 파라미터.

        Returns:
            MedicalDeviceResponse: 의료기기 품목 목록.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        body = self._fetch_json(self._MEDICAL_DEVICE_ENDPOINT, {
            "pageNo": str(request.page),
            "numOfRows": str(request.num_of_rows),
        })
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

    # -- 화장품 규제원료 --

    def get_cosmetics_regulations(self, request: CosmeticsReglRequest) -> CosmeticsReglResponse:
        """화장품 규제정보를 조회한다.

        Args:
            request: 조회 요청 파라미터.

        Returns:
            CosmeticsReglResponse: 규제 성분 목록.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        body = self._fetch_json(self._COSMETICS_REGL_ENDPOINT, {
            "pageNo": str(request.page),
            "numOfRows": str(request.num_of_rows),
        })
        raw_items = body.get("items", [])
        return CosmeticsReglResponse(
            total_count=body.get("totalCount", 0),
            items=[CosmeticsReglItem(**{k.lower(): v for k, v in item.items()}) for item in raw_items],
        )

    # -- 내부 공통 --

    def _fetch_json(self, endpoint: str, params: dict) -> dict:
        """식약처 API를 호출하고 body를 반환한다.

        Args:
            endpoint: API 엔드포인트 경로.
            params: 추가 쿼리 파라미터.

        Returns:
            dict: 응답 body (pageNo, totalCount, numOfRows, items 포함).
        """
        try:
            response = self._get(endpoint, params={
                "serviceKey": self._service_key,
                "type": "json",
                **params,
            })
        except httpx.HTTPStatusError as e:
            raise self._mask_url(e) from None
        data = self._parse_json(response)
        return data.get("body", {})
