"""법제처 소관 외부 API 클라이언트."""

from xml.etree.ElementTree import Element

from .base import BaseClient
from ..schemas.clients.law_request import LawSearchRequest, LawTextRequest
from ..schemas.clients.law_response import (
    AdmrulSearchItem,
    AdmrulSearchResponse,
    LawArticle,
    LawArticleSubItem,
    LawSearchItem,
    LawSearchResponse,
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
        """
        return self._fetch_text(request, target="admrul", id_param="ID")

    def get_eflaw_text(self, request: LawTextRequest) -> LawTextResponse:
        """시행법령 본문을 조회한다.

        Args:
            request: 본문 조회 요청 파라미터.

        Returns:
            LawTextResponse: 조문 목록이 담긴 본문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        return self._fetch_text(request, target="eflaw", id_param="MST")

    def get_licbyl_text(self, request: LawTextRequest) -> LawTextResponse:
        """자치법규 본문을 조회한다.

        Args:
            request: 본문 조회 요청 파라미터.

        Returns:
            LawTextResponse: 조문 목록이 담긴 본문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        return self._fetch_text(request, target="licbyl", id_param="ID")

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
            target: 검색 대상 (law, admrul, eflaw, licbyl).
            id_param: 일련번호 파라미터명 (law/eflaw은 MST, admrul/licbyl은 ID).

        Returns:
            LawTextResponse: 조문 목록이 담긴 본문 응답.
        """
        response = self._get(self._TEXT_ENDPOINT, params={
            "OC": self._oc,
            "target": target,
            id_param: request.mst,       # 일련번호
            "type": "XML",
        })
        root = self._parse_xml(response)
        self._check_api_error(root)

        # law/eflaw: <조문> > <조문단위> 구조
        articles_el = root.find("조문")
        if articles_el is not None:
            return LawTextResponse(
                articles=[
                    self._parse_article(el)
                    for el in articles_el.iter("조문단위")
                ],
            )

        # admrul: <조문내용> 태그가 루트 바로 아래 나열되는 구조
        content_els = root.findall("조문내용")
        if content_els:
            return LawTextResponse(
                articles=[
                    LawArticle(article_content=el.text)
                    for el in content_els
                    if el.text
                ],
            )

        return LawTextResponse(articles=[])

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
            paragraphs=self._parse_sub_items(el, "항", "항번호", "항내용"),
            items=self._parse_sub_items(el, "호", "호번호", "호내용"),
            sub_items=self._parse_sub_items(el, "목", "목번호", "목내용"),
            enforce_date=self._text(el, "조문시행일자"),
            reference=self._text(el, "조문참고자료"),
        )

    @staticmethod
    def _parse_sub_items(
        parent: Element,
        tag: str,
        number_tag: str,
        content_tag: str,
    ) -> list[LawArticleSubItem]:
        """항·호·목 하위 항목을 파싱한다.

        Args:
            parent: 부모 엘리먼트 (<조문단위> 또는 <항>).
            tag: 찾을 태그명 (항, 호, 목).
            number_tag: 번호 태그명.
            content_tag: 내용 태그명.

        Returns:
            list[LawArticleSubItem]: 파싱된 하위 항목 목록.
        """
        results = []
        for child in parent.iter(tag):
            num_el = child.find(number_tag)
            content_el = child.find(content_tag)
            results.append(LawArticleSubItem(
                number=num_el.text if num_el is not None else None,
                content=content_el.text if content_el is not None else None,
            ))
        return results

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
