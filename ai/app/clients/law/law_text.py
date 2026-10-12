"""법제처 법령 본문 클라이언트.

역할
    법령일련번호(MST)로 법령 본문(조문·항·호·목과 별표)을 조회.
    연혁 본문도 같은 요청에 그 시점 버전의 MST를 넣으면 받을 수 있음 (target=eflaw 본문은 HTML만 옴).
"""

from xml.etree.ElementTree import Element

import httpx

from .text_base import LawTextBaseClient
from ...schemas.clients.law_response import LawArticle, LawItem, LawParagraph, LawSubItem, LawTextResponse


class LawTextClient(LawTextBaseClient[LawTextResponse]):
    """법령 본문(target=law) 클라이언트."""

    _TARGET = "law"
    _ID_PARAM = "MST"
    _BASIC_INFO_TAG = "기본정보"

    def _parse(self, raw: httpx.Response) -> LawTextResponse:
        """법령 본문 XML 원문을 응답 스키마로 변환한다.

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
            mst=raw.request.url.params.get(self._ID_PARAM),     # 기본정보에 없어 요청값 사용
            name=self._text(info, "법령명_한글"),
            document_id=self._text(info, "법령ID"),
            law_type=self._text(info, "법종구분"),
            promulgate_date=self._text(info, "공포일자"),
            promulgate_number=self._text(info, "공포번호"),
            revision_type=self._text(info, "제개정구분"),
            enforce_date=self._text(info, "시행일자"),
            department=self._text(info, "소관부처"),
            articles=self._parse_articles(root),
            annexes=self._parse_annexes(root),
        )

    def _parse_articles(self, root: Element) -> list[LawArticle]:
        """조문 목록을 파싱하고 각 조문에 소속 편·장·절·관을 붙인다.

        <조문> > <조문단위> 중 조문여부가 "전문"인 행은 구획 제목이라 조문 목록에서 빼고 headings로만 남김.

        Args:
            root: 본문 XML 루트 엘리먼트.

        Returns:
            list[LawArticle]: 조문 목록. 조문이 없으면 빈 목록.
        """
        articles_el = root.find("조문")
        if articles_el is None:
            return []
        articles: list[LawArticle] = []
        headings: dict[str, str] = {}
        for el in articles_el.iter("조문단위"):
            if self._text(el, "조문여부") == "전문":
                updated = self._next_headings(headings, self._text(el, "조문내용") or "")
                if updated is not None:
                    headings = updated
                    continue
                # 구획 제목 모양이 아닌 전문 행은 내용 보존을 위해 조문으로 남김
            articles.append(self._parse_article(el, list(headings.values())))
        return articles

    def _parse_article(self, el: Element, headings: list[str]) -> LawArticle:
        """법령본문 조문 하나를 파싱한다.

        Args:
            el: <조문단위> 엘리먼트.
            headings: 소속 편·장·절·관 제목 (상위부터).

        Returns:
            LawArticle: 파싱된 조문. 항·호·목 포함.
        """
        return LawArticle(
            article_number=self._text(el, "조문번호"),
            article_branch_number=self._text(el, "조문가지번호"),
            article_is_exist=self._text(el, "조문여부"),
            article_title=self._text(el, "조문제목"),
            article_content=self._text(el, "조문내용"),
            paragraphs=[self._parse_paragraph(paragraph) for paragraph in el.findall("항")],
            enforce_date=self._text(el, "조문시행일자"),
            reference=self._text(el, "조문참고자료"),
            headings=headings,
        )

    def _parse_paragraph(self, el: Element) -> LawParagraph:
        """항 하나를 파싱한다. 직계 자식 호만 읽음.

        Args:
            el: <항> 엘리먼트.

        Returns:
            LawParagraph: 파싱된 항. 항번호 없이 호만 있으면 number·content가 None.
        """
        return LawParagraph(
            number=self._text(el, "항번호"),
            content=self._text(el, "항내용"),
            items=[self._parse_item(item) for item in el.findall("호")],
        )

    def _parse_item(self, el: Element) -> LawItem:
        """호 하나를 파싱한다. 직계 자식 목만 읽음.

        Args:
            el: <호> 엘리먼트.

        Returns:
            LawItem: 파싱된 호.
        """
        return LawItem(
            number=self._text(el, "호번호"),
            branch_number=self._text(el, "호가지번호"),
            content=self._text(el, "호내용"),
            sub_items=[self._parse_sub_item(sub_item) for sub_item in el.findall("목")],
        )

    def _parse_sub_item(self, el: Element) -> LawSubItem:
        """목 하나를 파싱한다.

        Args:
            el: <목> 엘리먼트.

        Returns:
            LawSubItem: 파싱된 목.
        """
        return LawSubItem(
            number=self._text(el, "목번호"),
            content=self._text(el, "목내용"),
        )
