"""법제처 법령 검색 클라이언트.

역할
    법령명 검색어로 현행 법령 목록(법령일련번호·법령ID·시행일 등)을 조회.
    본문 조회에 넣을 법령일련번호(MST)를 찾을 때 사용.
"""

from xml.etree.ElementTree import Element

import httpx

from .search_base import LawSearchBaseClient
from ...schemas.clients.law_response import LawSearchItem, LawSearchResponse


class LawSearchClient(LawSearchBaseClient[LawSearchResponse]):
    """법령 검색(target=law) 클라이언트."""

    _TARGET = "law"

    def _parse(self, raw: httpx.Response) -> LawSearchResponse:
        """법령 검색 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            LawSearchResponse: 검색 결과.

        Raises:
            RuntimeError: XML이 아니거나 법제처 오류 응답인 경우.
        """
        root = self._parse_root(raw)
        return LawSearchResponse(
            total_count=self._total_count(root),
            items=[self._parse_item(el) for el in root.iter("law")],
        )

    def _parse_item(self, el: Element) -> LawSearchItem:
        """법령 검색 항목을 파싱한다.

        Args:
            el: <law> 엘리먼트.

        Returns:
            LawSearchItem: 파싱된 검색 결과.
        """
        return LawSearchItem(
            mst=self._text(el, "법령일련번호"),
            law_id=self._text(el, "법령ID"),
            law_name=self._text(el, "법령명한글"),
            law_name_abbr=self._text(el, "법령약칭명"),
            law_type=self._text(el, "법령구분명"),
            promulgate_date=self._text(el, "공포일자"),
            promulgate_number=self._text(el, "공포번호"),
            enforce_date=self._text(el, "시행일자"),
            revision_type=self._text(el, "제개정구분명"),
            department=self._text(el, "소관부처명"),
        )
