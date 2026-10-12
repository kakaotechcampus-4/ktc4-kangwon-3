"""법제처 행정규칙 본문 클라이언트.

역할
    행정규칙일련번호로 고시·훈령·예규 본문(조문내용과 별표)을 조회.
    법령과 달리 조문이 구조화되지 않은 <조문내용> 문자열로만 옴.
"""

import httpx

from .text_base import LawTextBaseClient
from ...schemas.clients.law_response import LawArticle, LawTextResponse


class AdmrulTextClient(LawTextBaseClient):
    """행정규칙 본문(target=admrul) 클라이언트."""

    _TARGET = "admrul"
    _ID_PARAM = "ID"
    _BASIC_INFO_TAG = "행정규칙기본정보"

    def _parse(self, raw: httpx.Response) -> LawTextResponse:
        """행정규칙 본문 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            LawTextResponse: 기본정보와 조문·별표 목록이 담긴 본문 응답.

        Raises:
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 오류·기본정보 없는 응답).
        """
        root = self._parse_text_root(raw)
        info = root.find(self._BASIC_INFO_TAG)
        return LawTextResponse(
            name=self._text(info, "행정규칙명"),
            document_id=self._text(info, "행정규칙ID"),
            enforce_date=self._text(info, "시행일자"),
            department=self._text(info, "소관부처명"),
            # <조문내용> 태그가 루트 바로 아래 나열되는 구조
            articles=[LawArticle(article_content=el.text) for el in root.findall("조문내용") if el.text],
            annexes=self._parse_annexes(root),
        )
