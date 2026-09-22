"""국가기술표준원 제품안전정보센터 외부 API 클라이언트."""

import httpx

from .base import BaseClient
from ..schemas.clients.safety_korea_request import (
    CertDetailRequest,
    RecallDetailRequest,
    SafetyKoreaSearchRequest,
)
from ..schemas.clients.safety_korea_response import (
    CertItem,
    CertSearchResponse,
    ForeignRecallItem,
    ForeignRecallSearchResponse,
    RecallFile,
    RecallItem,
    RecallSearchResponse,
)


class SafetyKoreaClient(BaseClient):
    """국가기술표준원 제품안전정보센터(SafetyKorea) 클라이언트.

    방식 : GET/JSON
    인증 : AuthKey 헤더 (safetykorea.kr 자체 발급).
    비고
        KC인증정보 조회/상세, 국내리콜 조회/상세, 국외리콜 조회
        총 5개 엔드포인트를 제공한다.
    """

    _CERT_LIST = "/openapi/api/cert/certificationList.json"
    _CERT_DETAIL = "/openapi/api/cert/certificationDetail.json"
    _RECALL_LIST = "/openapi/api/recall/recallList.json"
    _RECALL_DETAIL = "/openapi/api/recall/recallDetail.json"
    _FOREIGN_RECALL_LIST = "/openapi/api/recall/fRecallList.json"

    def __init__(self, auth_key: str):
        super().__init__(
            base_url="https://www.safetykorea.kr",
            timeout=30.0,
            headers={"AuthKey": auth_key},
        )

    # -- KC인증정보 --

    def search_certifications(
        self, request: SafetyKoreaSearchRequest,
    ) -> CertSearchResponse:
        """KC인증정보를 검색한다.

        Args:
            request: 검색 요청. condition_key에 all, certNum,
                productName, modelName, certDate, signDate 사용 가능.

        Returns:
            CertSearchResponse: 인증정보 목록.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        data = self._fetch(self._CERT_LIST, {
            "conditionKey": request.condition_key,
            "conditionValue": request.condition_value,
        })
        raw_items = data.get("resultData") or []
        return CertSearchResponse(
            items=[CertItem(**item) for item in raw_items],
        )

    def get_certification_detail(self, request: CertDetailRequest) -> CertItem:
        """KC인증정보 상세를 조회한다.

        Args:
            request: 상세 조회 요청 (인증번호).

        Returns:
            CertItem: 인증정보 상세.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        data = self._fetch(self._CERT_DETAIL, {
            "certNum": request.cert_num,
        })
        raw = data.get("resultData") or {}
        return CertItem(**raw)

    # -- 국내리콜 --

    def search_recalls(
        self, request: SafetyKoreaSearchRequest,
    ) -> RecallSearchResponse:
        """국내리콜정보를 검색한다.

        Args:
            request: 검색 요청. condition_key에 all, barcodeNum,
                recallProductName, recallBrandName, recallModelName,
                certNum, publishDate 사용 가능.

        Returns:
            RecallSearchResponse: 리콜정보 목록.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        data = self._fetch(self._RECALL_LIST, {
            "conditionKey": request.condition_key,
            "conditionValue": request.condition_value,
        })
        raw_items = data.get("resultData") or []
        return RecallSearchResponse(
            items=[RecallItem(**item) for item in raw_items],
        )

    def get_recall_detail(self, request: RecallDetailRequest) -> RecallItem:
        """국내리콜 상세를 조회한다.

        Args:
            request: 상세 조회 요청 (리콜 아이디).

        Returns:
            RecallItem: 리콜정보 상세 (첨부파일 포함).

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        data = self._fetch(self._RECALL_DETAIL, {
            "recallUid": request.recall_uid,
        })
        raw = data.get("resultData") or {}
        if "recallFiles" in raw and raw["recallFiles"]:
            raw["recallFiles"] = [
                RecallFile(**f) for f in raw["recallFiles"]
            ]
        return RecallItem(**raw)

    # -- 국외리콜 --

    def search_foreign_recalls(
        self, request: SafetyKoreaSearchRequest,
    ) -> ForeignRecallSearchResponse:
        """국외리콜정보를 검색한다.

        Args:
            request: 검색 요청. condition_key에 all, recallProductName,
                recallBrandName, recallModelName, publishDate,
                fRecallUid 사용 가능.

        Returns:
            ForeignRecallSearchResponse: 국외리콜 목록.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        data = self._fetch(self._FOREIGN_RECALL_LIST, {
            "conditionKey": request.condition_key,
            "conditionValue": request.condition_value,
        })
        raw_items = data.get("resultData") or []
        return ForeignRecallSearchResponse(
            items=[ForeignRecallItem(**item) for item in raw_items],
        )

    # -- 내부 공통 --

    def _fetch(self, endpoint: str, params: dict) -> dict:
        """SafetyKorea API를 호출하고 응답 전체를 반환한다.

        Args:
            endpoint: API 엔드포인트 경로.
            params: 쿼리 파라미터.

        Returns:
            dict: 응답 JSON (resultCode, resultMsg, resultData 포함).

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
        """
        try:
            response = self._get(endpoint, params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                raise RuntimeError(
                    "SafetyKorea 인증 실패: AuthKey가 유효하지 않습니다 (302 Redirect)"
                ) from None
            raise
        return self._parse_json(response)
