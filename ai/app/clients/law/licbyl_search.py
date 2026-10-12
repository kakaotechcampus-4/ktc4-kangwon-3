"""법제처 별표·서식 검색 클라이언트.

역할
    별표명 검색어로 법령에 딸린 별표·서식 목록(관련 법령일련번호·별표번호·종류 등)을 조회.
    별표 본문은 관련 법령 본문에 함께 오므로, 여기서 찾은 관련 법령일련번호로 본문을 조회함.
"""

from xml.etree.ElementTree import Element

import httpx

from .search_base import LawSearchBaseClient
from ...schemas.clients.law_response import LicbylSearchItem, LicbylSearchResponse


class LicbylSearchClient(LawSearchBaseClient[LicbylSearchResponse]):
    """별표·서식 검색(target=licbyl) 클라이언트."""

    _TARGET = "licbyl"

    def _parse(self, raw: httpx.Response) -> LicbylSearchResponse:
        """별표·서식 검색 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            LicbylSearchResponse: 검색 결과.

        Raises:
            RuntimeError: XML이 아니거나 법제처 오류 응답인 경우.
        """
        root = self._parse_root(raw)
        return LicbylSearchResponse(
            total_count=self._total_count(root),
            items=[self._parse_item(el) for el in root.iter("licbyl")],
        )

    def _parse_item(self, el: Element) -> LicbylSearchItem:
        """별표·서식 검색 항목을 파싱한다.

        Args:
            el: <licbyl> 엘리먼트.

        Returns:
            LicbylSearchItem: 파싱된 검색 결과.
        """
        return LicbylSearchItem(
            serial_number=self._text(el, "별표일련번호"),
            related_law_mst=self._text(el, "관련법령일련번호"),
            related_law_id=self._text(el, "관련법령ID"),
            name=self._text(el, "별표명"),
            related_law_name=self._text(el, "관련법령명"),
            table_number=self._text(el, "별표번호"),
            table_type=self._text(el, "별표종류"),
            department=self._text(el, "소관부처명"),
            promulgate_date=self._text(el, "공포일자"),
            promulgate_number=self._text(el, "공포번호"),
            revision_type=self._text(el, "제개정구분명"),
            law_type=self._text(el, "법령종류"),
        )
