"""관세청 CLIP 국내 품목분류 결정사례 클라이언트."""

import re

import httpx

from ..base import BaseClient
from ...schemas.clients.customs_request import CLIPSearchRequest
from ...schemas.clients.customs_response import CLIPCase, CLIPSearchResponse


class CLIPClient(BaseClient[CLIPSearchRequest, CLIPSearchResponse]):
    """CLIP 국내 품목분류 결정사례 클라이언트.

    방식 : POST/form
    서비스 키 : 불필요
    비고
        X-Requested-With 헤더 필수.
        응답 본문은 JSON이지만 Content-Type은 text/html로 옴.
        응답에 <em> 태그가 섞여 오고 HS 코드에 점·하이픈이 포함됨 (예: 8414.59-9000).
    """

    _ENDPOINT = "/clip/prlstclsfsrch/retrieveDmstPrlstClsfCaseLst2.do"

    def __init__(self):
        super().__init__(
            base_url="https://unipass.customs.go.kr",
            # X-Requested-With 헤더가 없으면 JSON이 아닌 HTML 페이지가 응답됨
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def _send(self, request: CLIPSearchRequest) -> httpx.Response:
        """품목분류 결정사례 검색을 요청한다.

        페이지 번호는 `pageIndex`, 페이지당 건수는 `pageUnit`만 인식.

        Args:
            request: CLIP 검색 요청 파라미터.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        return self._post(self._ENDPOINT, data={
            "prlstClsfCaseTpcd": "01",                  # 01 = 국내 사례. 빠지면 400(Bad Request) 반환
            "srchYn": "Y",                              # 검색 실행 플래그
            "srwr": request.query,                      # 검색어
            "pageIndex": str(request.page),             # 페이지 번호
            "pageUnit": str(request.page_size),         # 페이지당 건수
        })

    def _parse(self, raw: httpx.Response) -> CLIPSearchResponse:
        """품목분류 결정사례 JSON 원문을 응답 스키마로 변환한다.

        페이지 정보는 서버가 실제 적용한 값(paginationInfo)을 사용.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            CLIPSearchResponse: 검색 결과.
        """
        body = self._parse_json(raw)
        uls = body.get("uls_dmst", {})
        pagination = body.get("paginationInfo", {})
        page = int(pagination.get("currentPageNo", 1))
        page_size = int(pagination.get("recordCountPerPage", 0))
        total_count = int(uls.get("thisTotalCount", 0))
        items = [self._parse_item(item) for item in uls.get("itemList", [])]

        return CLIPSearchResponse(
            page=page,
            total_count=total_count,
            # 빈 페이지면 끝으로 판단
            has_next=bool(items) and page * page_size < total_count,
            items=items,
        )

    def _parse_item(self, raw: dict) -> CLIPCase:
        """CLIP 응답 항목 하나를 정리한다.

        Args:
            raw: API 원본 항목.

        Returns:
            CLIPCase: em 태그 제거, HS 코드 숫자만 남기기가 적용된 항목.
        """
        return CLIPCase(
            # 결정된 HS 코드. 세관장확인은 숫자 10자리만 받으므로 점·하이픈을 모두 지운다 (예: 8414.59-9000 → 8414599000)
            hs_code=re.sub(r"\D", "", self._strip_html(raw.get("DTRM_HS_SGN", ""))),
            product_name=self._strip_html(raw.get("CMDT_NM", "")),          # 물품명
            description=self._strip_html(raw.get("CMDT_DESC", "")),         # 물품설명 (임베딩 대상)
            decision_reason=self._strip_html(raw.get("DTRM_RSN_CN", "")),   # 결정 이유
            doc_id=raw.get("DOCID"),                                        # 문서 ID
            enforce_date=raw.get("ENFR_DT"),                                # 시행일자
        )

    @staticmethod
    def _strip_html(text: str) -> str:
        """응답에 섞인 HTML 태그(<em> 등)를 제거한다.

        Args:
            text: 원본 문자열.

        Returns:
            str: 태그가 제거된 문자열.
        """
        return re.sub(r"<[^>]+>", "", text).strip()
