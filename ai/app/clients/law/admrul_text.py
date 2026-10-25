"""법제처 행정규칙 본문 클라이언트.

역할
    행정규칙일련번호로 고시·훈령·예규 본문(조문내용과 별표)을 조회.
    법령과 달리 조문이 구조화되지 않은 <조문내용> 문자열로만 옴.
    조문형 고시는 문자열에서 조문번호·제목, 항·호·목, 소속 편·장·절·관을 뽑아 법령 조문과 같은 모양으로 맞춤.
"""

import re
from xml.etree.ElementTree import Element

import httpx

from .text_base import LawTextBaseClient
from ...schemas.clients.law_response import (
    AdmrulTextResponse,
    LawArticle,
    LawAttachment,
    LawItem,
    LawParagraph,
    LawSubItem,
)

# 조문 머리 (예: "제1조(목적) …", "제6조의2(전문위원회 검토) …")
_ARTICLE_HEAD_RE = re.compile(r"^제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*(?:\(([^)]*)\))?")
# 조문 안 줄 머리: 항 "①", 호 "1." "1의2.", 목 "가."
_PARAGRAPH_RE = re.compile(r"^([①-⑳㉑-㉟])")
_ITEM_RE = re.compile(r"^(\d+(?:의\d+)?\.)")
_SUB_ITEM_RE = re.compile(r"^([가-힣]\.)")


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
        is_article_format = self._yes_no(self._text(info, "조문형식여부"))
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
            is_article_format=is_article_format,
            articles=self._parse_articles(root, is_article_format),
            annexes=self._parse_annexes(root),
            attachments=self._parse_attachments(root.find("첨부파일")),
        )

    def _parse_articles(self, root: Element, is_article_format: bool | None) -> list[LawArticle]:
        """<조문내용> 문자열 목록을 조문으로 파싱한다.

        <조문내용> 태그가 루트 바로 아래 나열되는 구조.
        조문형이면 구획 제목 줄("제1장 …")은 빼고 이후 조문의 headings로 붙이며, 조문 머리에서 번호·제목을 뽑음.
        비조문형(본문 한 덩어리)이면 문자열을 그대로 조문 하나씩으로 담음.

        Args:
            root: 본문 XML 루트 엘리먼트.
            is_article_format: 조문형식여부.

        Returns:
            list[LawArticle]: 조문 목록. 없으면 빈 목록.
        """
        contents = [el.text for el in root.findall("조문내용") if el.text and el.text.strip()]
        if not is_article_format:
            return [LawArticle(article_content=content) for content in contents]

        articles: list[LawArticle] = []
        headings: dict[str, str] = {}
        for content in contents:
            updated = self._next_headings(headings, content)
            if updated is not None:
                headings = updated
                continue
            match = _ARTICLE_HEAD_RE.match(content.strip())
            # 조문 머리가 없는 줄은 내용 보존을 위해 번호 없는 조문으로 남김
            if match is None:
                articles.append(LawArticle(article_content=content, headings=list(headings.values())))
                continue
            lead, paragraphs = self._split_article(content.strip(), match.end())
            articles.append(LawArticle(
                article_number=match.group(1),
                article_branch_number=match.group(2),
                article_is_exist="조문",
                article_title=match.group(3),
                article_content=lead,
                paragraphs=paragraphs,
                headings=list(headings.values()),
            ))
        return articles

    @staticmethod
    def _split_article(content: str, head_end: int) -> tuple[str, list[LawParagraph]]:
        """조문 문자열을 앞문장과 항·호·목으로 나눈다. 법령 조문(<조문내용>·<항>)과 같은 모양.

        줄 머리로 구분: 항 "①", 호 "1."·"1의2.", 목 "가.". 머리가 없는 줄은 바로 앞 요소에 이어 붙임.
        항 없이 호만 있으면 번호 없는 항 하나 아래에 호를 담음 (법령 원문과 같은 처리).

        Args:
            content: 조문 문자열 (예: "제3조(요건신청 방법) ① …\\n  ② …").
            head_end: 조문 머리("제3조(요건신청 방법)")가 끝나는 위치.

        Returns:
            tuple[str, list[LawParagraph]]: (앞문장, 항 목록). 항·호가 없으면 (조문 전체, []).
        """
        first, _, rest = content.partition("\n")
        lead_parts = [first[:head_end].strip()]
        lines = [first[head_end:]] + rest.split("\n")
        paragraphs: list[LawParagraph] = []
        item: LawItem | None = None
        sub_item: LawSubItem | None = None

        def append(target, text: str) -> None:
            target.content = f"{target.content}\n{text}" if target.content else text

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if match := _PARAGRAPH_RE.match(line):
                paragraphs.append(LawParagraph(number=match.group(1), content=line))
                item = sub_item = None
            elif match := _ITEM_RE.match(line):
                if not paragraphs:
                    paragraphs.append(LawParagraph())
                item = LawItem(number=match.group(1), content=line)
                paragraphs[-1].items.append(item)
                sub_item = None
            elif item is not None and (match := _SUB_ITEM_RE.match(line)):
                sub_item = LawSubItem(number=match.group(1), content=line)
                item.sub_items.append(sub_item)
            elif sub_item or item or paragraphs:
                append(sub_item or item or paragraphs[-1], line)
            else:
                lead_parts.append(line)
        return " ".join(part for part in lead_parts if part), paragraphs

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
