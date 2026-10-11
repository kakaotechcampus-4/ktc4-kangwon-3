"""관세청 세관장확인대상물품 GW 클라이언트.

역할
    HS 코드로 수입 통관 시 세관장확인(관세법 제226조)이 필요한 법령 요건을 조회.
    법령마다 요건확인기관·제출 서류·적용 시작일이 오고, 같은 법령이 확인기관 수만큼 반복됨.
    빈 목록은 통관 단계 확인이 없다는 뜻일 뿐 국내 판매 규제가 없다는 뜻은 아님.
"""

from urllib.parse import unquote
from xml.etree.ElementTree import Element

import httpx

from ..base import BaseClient
from ...schemas.clients.customs_request import CustomsGwConfirmationRequest
from ...schemas.clients.customs_response import (
    CustomsGwConfirmation,
    CustomsGwConfirmationResponse,
)


class CustomsGwClient(BaseClient[CustomsGwConfirmationRequest, CustomsGwConfirmationResponse]):
    """세관장확인대상물품 GW 클라이언트.

    방식 : GET/XML
    서비스 키 : data.go.kr serviceKey 필요.
    비고
        serviceKey는 URL 인코딩된 상태 그대로 전달.
        내부에서 디코딩 후 httpx params로 넘겨 이중 인코딩 방지.
    """

    _ENDPOINT = "/1220000/retrieveCcctLworCd/getRetrieveCcctLworCd"

    def __init__(self, service_key: str):
        super().__init__(base_url="https://apis.data.go.kr")
        self._service_key = unquote(service_key)

    def _send(self, request: CustomsGwConfirmationRequest) -> httpx.Response:
        """HS 코드로 세관장확인대상물품 조회를 요청한다.

        Args:
            request: 세관장확인대상물품 조회 요청 파라미터.

        Returns:
            httpx.Response: XML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 서비스 키는 마스킹됨.
        """
        try:
            return self._get(self._ENDPOINT, params={
                "serviceKey": self._service_key,            # 서비스 키
                "hsSgn": request.hs_code,                   # HS 품목코드 (10자리, 하이픈 없음)
                "imexTpcd": request.import_export,          # 수입/수출 구분
            })
        except httpx.HTTPStatusError as e:
            raise self._mask_url(e) from None

    def _parse(self, raw: httpx.Response) -> CustomsGwConfirmationResponse:
        """세관장확인대상물품 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            CustomsGwConfirmationResponse: 확인대상물품 조회 결과.
        """
        root = self._parse_xml(raw)
        return CustomsGwConfirmationResponse(
            items=self._parse_items(root),
        )

    def _parse_items(self, root: Element) -> list[CustomsGwConfirmation]:
        """세관장확인대상물품 XML 응답을 파싱한다.

        Args:
            root: XML 루트 엘리먼트.

        Returns:
            list[CustomsGwConfirmation]: 파싱된 확인대상물품 목록.
        """
        items = []
        for item in root.iter("item"):
            items.append(CustomsGwConfirmation(
                hs_code=self._text(item, "hsSgn"),                          # 조회한 HS 코드
                law_code=self._text(item, "dcerCfrmLworCd"),                # 법령 코드
                law_name=self._text(item, "dcerCfrmLworNm"),                # 법령 이름
                req_agency_code=self._text(item, "reqApreIttCd"),           # 조회 요청기관 코드
                req_agency_name=self._text(item, "reqApreIttNm"),           # 조회 요청기관 이름
                req_document_name=self._text(item, "reqCfrmIstmNm"),        # 제출 서류명
                apply_start_date=self._text(item, "aplyStrtDt"),            # 적용 시작일
            ))
        return items

    @staticmethod
    def _text(element: Element, tag: str) -> str | None:
        """XML 엘리먼트에서 태그의 텍스트를 꺼낸다.

        Args:
            element: 부모 엘리먼트.
            tag: 찾을 태그명.

        Returns:
            str | None: 태그 텍스트. 없으면 None.
        """
        child = element.find(tag)
        return child.text if child is not None else None
