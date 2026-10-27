"""법제처 목록 조회(lawSearch.do) 클라이언트 공통 베이스."""

from typing import ClassVar
from xml.etree.ElementTree import Element

import httpx

from .base import LawGoKrClient
from ..request import ResponseT
from ...schemas.clients.law_request import LawSearchRequest


class LawSearchBaseClient(LawGoKrClient[LawSearchRequest, ResponseT]):
    """법제처 목록 조회(lawSearch.do) 공통 베이스.

    법령·시행법령·행정규칙·별표서식 검색이 같은 요청 형식(target·query·display)을 씀.
    하위 클라이언트는 `_TARGET`과 `_parse`만 구현.
    """

    _ENDPOINT = "/DRF/lawSearch.do"
    _TARGET: ClassVar[str]

    def _send(self, request: LawSearchRequest) -> httpx.Response:
        """검색어로 목록 조회를 요청한다.

        Args:
            request: 검색 요청 파라미터.

        Returns:
            httpx.Response: XML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 OC는 마스킹됨.
        """
        return self._get_with_oc(self._ENDPOINT, params={
            "target": self._TARGET,                 # 검색 대상
            "query": request.query,                 # 검색어
            "display": str(request.display),        # 결과 건수
            **self._extra_params(),
        })

    def _extra_params(self) -> dict[str, str]:
        """하위 클라이언트가 생성 시 고정한 추가 검색 조건. 기본은 없음."""
        return {}

    def _total_count(self, root: Element) -> int:
        """검색 응답의 전체 건수를 꺼낸다.

        Args:
            root: 검색 응답 XML 루트 엘리먼트.

        Returns:
            int: 전체 검색 건수. 없으면 0.
        """
        return int(self._text(root, "totalCnt") or "0")
