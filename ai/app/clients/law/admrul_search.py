"""법제처 행정규칙 검색 클라이언트.

역할
    행정규칙명 검색어로 고시·훈령·예규 목록(행정규칙일련번호·ID·시행일 등)을 조회.
    본문 조회에 넣을 행정규칙일련번호를 찾을 때 사용.
"""

from xml.etree.ElementTree import Element

import httpx

from .search_base import LawSearchBaseClient
from ...schemas.clients.law_response import AdmrulSearchItem, AdmrulSearchResponse


class AdmrulSearchClient(LawSearchBaseClient[AdmrulSearchResponse]):
    """행정규칙 검색(target=admrul) 클라이언트."""

    _TARGET = "admrul"

    def _parse(self, raw: httpx.Response) -> AdmrulSearchResponse:
        """행정규칙 검색 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            AdmrulSearchResponse: 검색 결과.

        Raises:
            RuntimeError: XML이 아니거나 법제처 오류 응답인 경우.
        """
        root = self._parse_root(raw)
        return AdmrulSearchResponse(
            total_count=self._total_count(root),
            items=[self._parse_item(el) for el in root.iter("admrul")],
        )

    def _parse_item(self, el: Element) -> AdmrulSearchItem:
        """행정규칙 검색 항목을 파싱한다.

        Args:
            el: <admrul> 엘리먼트.

        Returns:
            AdmrulSearchItem: 파싱된 검색 결과.
        """
        return AdmrulSearchItem(
            serial_number=self._text(el, "행정규칙일련번호"),
            name=self._text(el, "행정규칙명"),
            rule_type=self._text(el, "행정규칙종류"),
            issue_date=self._text(el, "발령일자"),
            issue_number=self._text(el, "발령번호"),
            department=self._text(el, "소관부처명"),
            enforce_date=self._text(el, "시행일자"),
            revision_type=self._text(el, "제개정구분명"),
            rule_id=self._text(el, "행정규칙ID"),
            history_status=self._text(el, "현행연혁구분"),
        )
