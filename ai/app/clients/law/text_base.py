"""법제처 본문 조회(lawService.do) 클라이언트 공통 베이스."""

from typing import ClassVar
from xml.etree.ElementTree import Element

import httpx

from .base import LawGoKrClient
from ...schemas.clients.law_request import LawTextRequest
from ...schemas.clients.law_response import LawAnnex, LawTextResponse


class LawTextBaseClient(LawGoKrClient[LawTextRequest, LawTextResponse]):
    """법제처 본문 조회(lawService.do) 공통 베이스.

    법령·행정규칙 본문이 같은 요청 형식(target·일련번호)과 별표 구조를 씀.
    하위 클라이언트는 `_TARGET`·`_ID_PARAM`·`_BASIC_INFO_TAG`와 `_parse`만 구현.
    """

    _ENDPOINT = "/DRF/lawService.do"
    _TARGET: ClassVar[str]
    _ID_PARAM: ClassVar[str]           # 일련번호 파라미터명 (law: MST, admrul: ID)
    _BASIC_INFO_TAG: ClassVar[str]     # 정상 본문에만 있는 기본정보 태그

    def _send(self, request: LawTextRequest) -> httpx.Response:
        """일련번호로 본문 조회를 요청한다.

        Args:
            request: 본문 조회 요청 파라미터.

        Returns:
            httpx.Response: XML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 OC는 마스킹됨.
        """
        return self._get_with_oc(self._ENDPOINT, params={
            "target": self._TARGET,             # 본문 대상
            self._ID_PARAM: request.mst,        # 일련번호
        })

    def _parse_text_root(self, raw: httpx.Response) -> Element:
        """본문 원문을 XML로 해석하고, 본문을 받지 못한 응답을 걸러낸다.

        법제처는 요청이 잘못되면 본문 대신 HTML 안내 페이지나 수백 B짜리 안내 XML을 성공으로 돌려줌.
        빈 결과로 넘기면 "받지 못한 것"과 "받았는데 조문이 없는 것"을 호출하는 쪽에서 구분할 수 없음.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            Element: XML 루트 엘리먼트.

        Raises:
            RuntimeError: XML이 아니거나(HTML 등), 법제처 오류 응답이거나, 기본정보가 없는 응답인 경우.
        """
        root = self._parse_root(raw)
        # 없는 번호 → <Law>안내 문장</Law>, 파싱되는 XHTML 안내 페이지 → html 루트 (둘 다 기본정보 없음)
        if root.find(self._BASIC_INFO_TAG) is None:
            id_value = raw.request.url.params.get(self._ID_PARAM)
            notice = (root.text or "").strip()[:40]
            raise RuntimeError(
                f"법제처 본문 수신 실패: 기본정보 없음 (target={self._TARGET}, id={id_value}, "
                f"응답 {len(raw.content):,}B, 루트 {root.tag}: {notice})"
            )
        return root

    def _parse_annexes(self, root: Element) -> list[LawAnnex]:
        """본문의 별표 목록을 파싱한다.

        별표(품목표 등)는 조문과 별개로 <별표> > <별표단위> 아래에 옴.

        Args:
            root: 본문 XML 루트 엘리먼트.

        Returns:
            list[LawAnnex]: 별표 목록. 없으면 빈 목록.
        """
        return [self._parse_annex(el) for el in root.iter("별표단위")]

    def _parse_annex(self, el: Element) -> LawAnnex:
        """별표 하나를 파싱한다. 파일 링크는 파싱 쉬운 형식 하나만 담음.

        Args:
            el: <별표단위> 엘리먼트.

        Returns:
            LawAnnex: 파싱된 별표.
        """
        # 형식은 링크와 짝인 파일명 확장자로 정함 (파일명이 없으면 태그 이름 기준)
        file_url, file_type = self._pick_file([
            (self._text(el, "별표서식PDF파일링크"), self._file_type(self._text(el, "별표PDF파일명")) or "pdf"),
            (self._text(el, "별표서식파일링크"), self._file_type(self._text(el, "별표HWP파일명")) or "hwp"),
            (self._text(el, "별표서식이미지파일링크"), self._file_type(self._text(el, "별표이미지파일명"))),
        ])
        return LawAnnex(
            annex_number=self._text(el, "별표번호"),
            annex_branch_number=self._text(el, "별표가지번호"),
            annex_type=self._text(el, "별표구분"),
            annex_title=self._text(el, "별표제목"),
            annex_content=self._text(el, "별표내용"),
            file_url=file_url,
            file_type=file_type,
        )
