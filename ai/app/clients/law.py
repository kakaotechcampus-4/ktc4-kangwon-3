"""법제처 소관 외부 API 클라이언트."""

from xml.etree.ElementTree import Element, ParseError

import httpx

from .base import BaseClient
from ..schemas.clients.law_request import LawSearchRequest, LawTextRequest, LicbylTextRequest
from ..schemas.clients.law_response import (
    AdmrulSearchItem,
    AdmrulSearchResponse,
    LawAnnex,
    LawArticle,
    LawItem,
    LawParagraph,
    LawSearchItem,
    LawSearchResponse,
    LawSubItem,
    LawTextResponse,
    LicbylSearchItem,
    LicbylSearchResponse,
)


class LawClient(BaseClient):
    """법제처 법령정보 클라이언트.

    방식 : GET/XML
    서비스 키 : OC 값 (기본 test).
    비고
        법령검색과 법령본문 두 엔드포인트를 제공한다.
        XML 태그명이 한글이며, 텍스트에 CDATA가 포함된다.
    """

    _SEARCH_ENDPOINT = "/DRF/lawSearch.do"
    _TEXT_ENDPOINT = "/DRF/lawService.do"
    # 정상 본문에만 있는 기본정보 태그 (law: 기본정보, admrul: 행정규칙기본정보)
    _BASIC_INFO_TAGS = ("기본정보", "행정규칙기본정보")

    def __init__(self, oc: str = "test"):
        super().__init__(
            base_url="https://www.law.go.kr",
            # 법령본문 응답이 커서 timeout을 넉넉하게 설정 (전파법 기준 ~200KB)
            timeout=30.0,
        )
        self._oc = oc

    # -- 법령검색 (target별) --

    def search_law(self, request: LawSearchRequest) -> LawSearchResponse:
        """법령을 검색한다.

        Args:
            request: 검색 요청 파라미터.

        Returns:
            LawSearchResponse: 검색 결과.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        root = self._fetch_search(request, target="law")
        return LawSearchResponse(
            total_count=int(self._text(root, "totalCnt") or "0"),
            items=[self._parse_law_item(el) for el in root.iter("law")],
        )

    def search_admrul(self, request: LawSearchRequest) -> AdmrulSearchResponse:
        """행정규칙을 검색한다.

        Args:
            request: 검색 요청 파라미터.

        Returns:
            AdmrulSearchResponse: 검색 결과.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        root = self._fetch_search(request, target="admrul")
        return AdmrulSearchResponse(
            total_count=int(self._text(root, "totalCnt") or "0"),
            items=[self._parse_admrul_item(el) for el in root.iter("admrul")],
        )

    def search_eflaw(self, request: LawSearchRequest) -> LawSearchResponse:
        """시행법령을 검색한다.

        Args:
            request: 검색 요청 파라미터.

        Returns:
            LawSearchResponse: 검색 결과.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        root = self._fetch_search(request, target="eflaw")
        return LawSearchResponse(
            total_count=int(self._text(root, "totalCnt") or "0"),
            items=[self._parse_law_item(el) for el in root.iter("law")],
        )

    def search_licbyl(self, request: LawSearchRequest) -> LicbylSearchResponse:
        """자치법규(별표서식)를 검색한다.

        Args:
            request: 검색 요청 파라미터.

        Returns:
            LicbylSearchResponse: 검색 결과.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        root = self._fetch_search(request, target="licbyl")
        return LicbylSearchResponse(
            total_count=int(self._text(root, "totalCnt") or "0"),
            items=[self._parse_licbyl_item(el) for el in root.iter("licbyl")],
        )

    # -- 법령본문 (target별) --

    def get_law_text(self, request: LawTextRequest) -> LawTextResponse:
        """법령 본문을 조회한다.

        Args:
            request: 본문 조회 요청 파라미터.

        Returns:
            LawTextResponse: 조문 목록이 담긴 본문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 기본정보가 없는 응답).
        """
        return self._fetch_text(request, target="law", id_param="MST")

    def get_admrul_text(self, request: LawTextRequest) -> LawTextResponse:
        """행정규칙 본문을 조회한다.

        Args:
            request: 본문 조회 요청 파라미터.

        Returns:
            LawTextResponse: 조문 목록이 담긴 본문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 기본정보가 없는 응답).
        """
        return self._fetch_text(request, target="admrul", id_param="ID")

    def get_eflaw_text(self, request: LawTextRequest) -> LawTextResponse:
        """시행법령(연혁 포함) 본문을 조회한다.

        target=eflaw는 검색 전용이라 본문을 요청하면 HTML이 온다.
        연혁 본문은 target=law에 그 시점 버전의 MST를 넣어야 받을 수 있다.

        Args:
            request: 본문 조회 요청 파라미터. mst에는 search_eflaw() 결과의 버전별 mst를 넣는다.

        Returns:
            LawTextResponse: 해당 버전의 조문·별표 목록이 담긴 본문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 기본정보가 없는 응답).
        """
        return self._fetch_text(request, target="law", id_param="MST")

    def get_licbyl_text(self, request: LicbylTextRequest) -> LawAnnex:
        """별표·서식 본문을 조회한다.

        target=licbyl은 검색 전용이라 본문을 요청하면 HTML 껍데기가 온다.
        별표 본문은 관련 법령 본문(target=law)에 함께 오므로, 그 안에서 번호와 종류가 맞는 별표를 골라 반환한다.

        Args:
            request: 별표 조회 요청 파라미터. search_licbyl() 결과의 관련 법령 MST, 별표번호, 별표종류를 넣는다.

        Returns:
            LawAnnex: 요청한 별표·서식 본문.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
            RuntimeError: 본문을 받지 못했거나, 관련 법령 본문에 요청한 별표가 없는 경우.
        """
        text = self._fetch_text(LawTextRequest(mst=request.related_law_mst), target="law", id_param="MST")

        # 검색 결과 별표번호 "000300" = 본문 별표번호 "0003" + 별표가지번호 "00"
        number, branch = request.table_number[:4], request.table_number[4:]
        for annex in text.annexes:
            if (annex.annex_number, annex.annex_branch_number, annex.annex_type) == (number, branch, request.table_type):
                return annex

        # 빈 결과로 넘기면 "별표 내용 없음"으로 읽히므로 수신 실패와 같이 예외로 올린다
        raise RuntimeError(
            f"법제처 별표 조회 실패: 관련 법령 본문에 요청한 별표가 없음 "
            f"(mst={request.related_law_mst}, 별표번호={request.table_number}, 종류={request.table_type})"
        )

    # -- 내부 공통 --

    def _fetch_search(self, request: LawSearchRequest, target: str) -> Element:
        """법령검색 API를 호출하고 XML 루트를 반환한다.

        Args:
            request: 검색 요청 파라미터.
            target: 검색 대상 (law, admrul, eflaw, licbyl).

        Returns:
            Element: 파싱된 XML 루트 엘리먼트.
        """
        response = self._get(self._SEARCH_ENDPOINT, params={
            "OC": self._oc,
            "target": target,            # 검색 대상
            "type": "XML",               # 응답 포맷
            "query": request.query,      # 검색어
            "display": str(request.display),  # 결과 건수
        })
        root = self._parse_xml(response)
        self._check_api_error(root)
        return root

    def _fetch_text(self, request: LawTextRequest, target: str, id_param: str) -> LawTextResponse:
        """법령본문 조회 공통 로직.

        Args:
            request: 본문 조회 요청 파라미터.
            target: 본문 대상 (law, admrul). eflaw·licbyl 본문도 target=law로 조회한다.
            id_param: 일련번호 파라미터명 (law는 MST, admrul은 ID).

        Returns:
            LawTextResponse: 조문·별표 목록이 담긴 본문 응답.

        Raises:
            RuntimeError: 본문을 받지 못한 경우 (XML이 아니거나 기본정보가 없는 응답).
        """
        response = self._get(self._TEXT_ENDPOINT, params={
            "OC": self._oc,
            "target": target,
            id_param: request.mst,       # 일련번호
            "type": "XML",
        })
        root = self._parse_text_root(response, target, request.mst)
        info = self._parse_text_info(root)

        # 별표(품목표 등)는 조문과 별개로 <별표> > <별표단위> 아래에 오게 됨
        annexes = [self._parse_annex(el) for el in root.iter("별표단위")]

        # law/eflaw: <조문> > <조문단위> 구조
        articles_el = root.find("조문")
        if articles_el is not None:
            return LawTextResponse(
                **info,
                articles=[
                    self._parse_article(el)
                    for el in articles_el.iter("조문단위")
                ],
                annexes=annexes,
            )

        # admrul: <조문내용> 태그가 루트 바로 아래 나열되는 구조
        content_els = root.findall("조문내용")
        if content_els:
            return LawTextResponse(
                **info,
                articles=[
                    LawArticle(article_content=el.text)
                    for el in content_els
                    if el.text
                ],
                annexes=annexes,
            )

        return LawTextResponse(**info, articles=[], annexes=annexes)

    def _parse_text_info(self, root: Element) -> dict[str, str | None]:
        """본문 응답의 기본정보를 파싱한다.

        Args:
            root: 본문 응답 XML 루트 엘리먼트.

        Returns:
            dict[str, str | None]: LawTextResponse의 기본정보 필드. 기본정보가 없으면 빈 dict.
        """
        # law/eflaw: <기본정보> 아래 법령명_한글, 법령ID, 소관부처
        law_info = root.find("기본정보")
        if law_info is not None:
            return {
                "name": self._text(law_info, "법령명_한글"),
                "document_id": self._text(law_info, "법령ID"),
                "enforce_date": self._text(law_info, "시행일자"),
                "department": self._text(law_info, "소관부처"),
            }

        # admrul: <행정규칙기본정보> 아래 행정규칙명, 행정규칙ID, 소관부처명
        admrul_info = root.find("행정규칙기본정보")
        if admrul_info is not None:
            return {
                "name": self._text(admrul_info, "행정규칙명"),
                "document_id": self._text(admrul_info, "행정규칙ID"),
                "enforce_date": self._text(admrul_info, "시행일자"),
                "department": self._text(admrul_info, "소관부처명"),
            }

        return {}

    def _parse_text_root(self, response: httpx.Response, target: str, id_value: str) -> Element:
        """본문 응답을 XML로 파싱하고, 본문을 받지 못한 응답을 걸러낸다.

        법제처는 요청이 잘못되면 본문 대신 HTML 안내 페이지나 수백 B짜리 안내 XML을 성공으로 돌려준다.
        이를 빈 결과로 넘기면 "받지 못한 것"과 "받았는데 조문이 없는 것"을 호출하는 쪽에서 구분할 수 없다.

        Args:
            response: 본문 조회 HTTP 응답.
            target: 검색 대상 (예외 메시지용).
            id_value: 요청한 일련번호 (예외 메시지용).

        Returns:
            Element: 파싱된 XML 루트 엘리먼트.

        Raises:
            RuntimeError: API 에러 응답이거나, XML이 아니거나(HTML 등), 기본정보가 없는 응답인 경우.
        """
        where = f"target={target}, id={id_value}, 응답 {len(response.content):,}B"

        try:
            root = self._parse_xml(response)
        except ParseError as e:
            raise RuntimeError(f"법제처 본문 수신 실패: XML이 아닌 응답 ({where})") from e

        self._check_api_error(root)

        # 없는 번호 → <Law>안내 문장</Law>, 파싱되는 XHTML 안내 페이지 → html 루트 (둘 다 기본정보 없음)
        if not any(root.find(tag) is not None for tag in self._BASIC_INFO_TAGS):
            notice = (root.text or "").strip()[:40]
            raise RuntimeError(f"법제처 본문 수신 실패: 기본정보 없음 ({where}, 루트 {root.tag}: {notice})")
        return root

    @staticmethod
    def _check_api_error(root: Element) -> None:
        """법제처 API 에러 응답을 감지한다.

        Args:
            root: 파싱된 XML 루트 엘리먼트.

        Raises:
            RuntimeError: API가 에러 응답(<Response>)을 반환한 경우.
        """
        if root.tag != "Response":
            return
        result = root.findtext("result", "")
        msg = root.findtext("msg", "")
        raise RuntimeError(f"법제처 API 오류: {result} — {msg}")

    # -- target별 검색결과 파싱 --

    def _parse_law_item(self, el: Element) -> LawSearchItem:
        """법령/시행법령 검색 항목을 파싱한다.

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

    def _parse_admrul_item(self, el: Element) -> AdmrulSearchItem:
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
        )

    def _parse_licbyl_item(self, el: Element) -> LicbylSearchItem:
        """자치법규(별표서식) 검색 항목을 파싱한다.

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

    def _parse_article(self, el: Element) -> LawArticle:
        """법령본문 조문 하나를 파싱한다.

        Args:
            el: <조문단위> 엘리먼트.

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
        )

    def _parse_annex(self, el: Element) -> LawAnnex:
        """법령본문 별표 하나를 파싱한다.

        Args:
            el: <별표단위> 엘리먼트.

        Returns:
            LawAnnex: 파싱된 별표.
        """
        return LawAnnex(
            annex_number=self._text(el, "별표번호"),
            annex_branch_number=self._text(el, "별표가지번호"),
            annex_type=self._text(el, "별표구분"),
            annex_title=self._text(el, "별표제목"),
            annex_content=self._text(el, "별표내용"),
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
