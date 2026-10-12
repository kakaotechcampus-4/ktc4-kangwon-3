"""법제처 행정규칙 본문 클라이언트.

역할
    행정규칙일련번호로 고시·훈령·예규 본문(조문내용과 별표)을 조회.
    법령과 달리 조문이 구조화되지 않은 <조문내용> 문자열로만 옴.
"""

from xml.etree.ElementTree import Element

import httpx

from .text_base import LawTextBaseClient
from ...schemas.clients.law_response import AdmrulTextResponse, LawArticle, LawAttachment


class AdmrulTextClient(LawTextBaseClient[AdmrulTextResponse]):
    """행정규칙 본문(target=admrul) 클라이언트."""

    _TARGET = "admrul"
    _ID_PARAM = "ID"
    _BASIC_INFO_TAG = "행정규칙기본정보"

    def _parse(self, raw: httpx.Response) -> AdmrulTextResponse:
        """행정규칙 본문 XML 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            AdmrulTextResponse: 기본정보와 조문·별표·첨부파일 목록이 담긴 본문 응답.

        Raises:
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 오류·기본정보 없는 응답).
        """
        root = self._parse_text_root(raw)
        info = root.find(self._BASIC_INFO_TAG)
        return AdmrulTextResponse(
            serial_number=self._text(info, "행정규칙일련번호"),
            name=self._text(info, "행정규칙명"),
            document_id=self._text(info, "행정규칙ID"),
            rule_type=self._text(info, "행정규칙종류"),
            issue_date=self._text(info, "발령일자"),
            issue_number=self._text(info, "발령번호"),
            revision_type=self._text(info, "제개정구분명"),
            enforce_date=self._text(info, "시행일자"),
            department=self._text(info, "소관부처명"),
            is_current=self._yes_no(self._text(info, "현행여부")),
            is_article_format=self._yes_no(self._text(info, "조문형식여부")),
            # <조문내용> 태그가 루트 바로 아래 나열되는 구조
            articles=[LawArticle(article_content=el.text) for el in root.findall("조문내용") if el.text],
            annexes=self._parse_annexes(root),
            attachments=self._parse_attachments(root.find("첨부파일")),
        )

    def _parse_attachments(self, el: Element | None) -> list[LawAttachment]:
        """첨부파일 목록을 파싱한다. 같은 문서의 다른 형식은 하나로 묶고 링크 하나만 남김.

        <첨부파일> 아래 <첨부파일명>·<첨부파일링크>가 같은 순서로 반복됨.
        파일명에서 확장자를 뺀 이름이 같으면 같은 문서로 봄 (예: 고시전문.pdf, 고시전문.hwpx).

        Args:
            el: <첨부파일> 엘리먼트. 없으면 None.

        Returns:
            list[LawAttachment]: 첨부파일 목록 (원문 순서). 없으면 빈 목록.
        """
        if el is None:
            return []
        names = [(child.text or "").strip() for child in el.findall("첨부파일명")]
        links = [child.text for child in el.findall("첨부파일링크")]
        grouped: dict[str, list[tuple[str | None, str | None]]] = {}
        for name, link in zip(names, links):
            stem = name.rsplit(".", 1)[0] if "." in name else name
            grouped.setdefault(stem, []).append((link, self._file_type(name)))
        attachments = []
        for stem, candidates in grouped.items():
            file_url, file_type = self._pick_file(candidates)
            if file_url:
                attachments.append(LawAttachment(name=stem, file_url=file_url, file_type=file_type))
        return attachments

    @staticmethod
    def _yes_no(value: str | None) -> bool | None:
        """Y/N 값을 bool로 바꾼다.

        Args:
            value: "Y" 또는 "N".

        Returns:
            bool | None: Y면 True, N이면 False, 그 밖의 값이면 None.
        """
        return {"Y": True, "N": False}.get((value or "").strip().upper())
