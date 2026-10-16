"""법제처 국가법령정보 공동활용(law.go.kr DRF) 클라이언트 공통 베이스."""

from xml.etree.ElementTree import Element, ParseError

import httpx

from ..base import BaseClient, RequestT, ResponseT

_BASE_URL = "https://www.law.go.kr"

# 별표·첨부 파일 형식 우선순위 (표 구조가 남는 순). 목록에 없는 형식은 맨 뒤
# HWPX·HWP는 칸 주소·병합이 파일에 그대로 있어 표를 정확히 복원. PDF는 선·글자 위치로 추정
_FILE_TYPE_PRIORITY = ("hwpx", "hwp", "xlsx", "pdf", "gif", "png", "jpg", "jpeg", "zip")


class LawGoKrClient(BaseClient[RequestT, ResponseT]):
    """법제처 국가법령정보 공동활용 API 공통 베이스.

    방식 : GET/XML
    서비스 키 : OC 값 필요 (law.go.kr 발급, 기본값 없음).
    비고
        XML 태그명이 한글이며, 텍스트에 CDATA가 포함됨.
        요청 오류는 HTTP 200에 <Response><result>·<msg> 형식으로 옴.
        하위 클라이언트는 `_get_with_oc`로 요청하고 `_send`·`_parse`를 구현.

    Args:
        oc: law.go.kr 발급 OC 값.

    Raises:
        ValueError: OC 값이 비어 있는 경우.
    """

    def __init__(self, oc: str):
        if not oc or not oc.strip():
            raise ValueError("법제처 OC 값이 비어 있음 (LAW_GO_KR_OC)")
        super().__init__(
            base_url=_BASE_URL,
            # 법령본문 응답이 커서 timeout을 넉넉하게 설정 (전파법 기준 ~200KB)
            timeout=30.0,
        )
        self._oc = oc

    def _get_with_oc(self, path: str, params: dict) -> httpx.Response:
        """OC와 XML 형식 지정을 붙여 GET 요청을 보낸다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: OC·type을 뺀 쿼리 파라미터.

        Returns:
            httpx.Response: XML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우. 메시지의 OC는 마스킹됨.
        """
        try:
            return self._get(path, params={"OC": self._oc, "type": "XML", **params})
        except httpx.HTTPStatusError as e:
            raise self._mask_url(e) from None

    def _parse_root(self, raw: httpx.Response) -> Element:
        """원문을 XML로 해석하고 법제처 오류 응답을 걸러낸다.

        Args:
            raw: `_send`가 받은 XML 원문 응답.

        Returns:
            Element: XML 루트 엘리먼트.

        Raises:
            RuntimeError: XML이 아닌 응답(HTML 안내 페이지 등)이거나 <Response> 오류 응답인 경우.
        """
        try:
            root = self._parse_xml(raw)
        except ParseError as e:
            raise RuntimeError(f"법제처 응답 수신 실패: XML이 아닌 응답 (응답 {len(raw.content):,}B)") from e
        if root.tag == "Response":
            raise RuntimeError(f"법제처 API 오류: {root.findtext('result', '')} — {root.findtext('msg', '')}")
        return root

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

    @staticmethod
    def _file_type(filename: str | None) -> str | None:
        """파일명에서 형식(확장자)을 꺼낸다.

        Args:
            filename: 파일명 (예: law0120572025100100156KC_000100F.pdf).

        Returns:
            str | None: 소문자 확장자 (예: pdf). 파일명이 없거나 확장자가 없으면 None.
        """
        if not filename or "." not in filename.strip():
            return None
        return filename.strip().rsplit(".", 1)[1].lower()

    @staticmethod
    def _pick_file(candidates: list[tuple[str | None, str | None]]) -> tuple[str | None, str | None]:
        """같은 내용의 파일 링크 여러 개 중 파싱하기 쉬운 형식 하나를 고른다.

        우선순위는 HWPX → HWP → XLSX → PDF → 이미지 → ZIP. 경로만 온 링크는 완전한 주소로 바꿈.

        Args:
            candidates: (링크, 형식) 목록. 링크가 비어 있는 항목은 건너뜀.

        Returns:
            tuple[str | None, str | None]: (완전한 링크, 형식). 링크가 하나도 없으면 (None, None).
        """
        available = [(link.strip(), file_type) for link, file_type in candidates if link and link.strip()]
        if not available:
            return None, None

        def rank(item: tuple[str, str | None]) -> int:
            file_type = item[1]
            return _FILE_TYPE_PRIORITY.index(file_type) if file_type in _FILE_TYPE_PRIORITY else len(_FILE_TYPE_PRIORITY)

        link, file_type = min(available, key=rank)
        # 별표 링크는 경로만 옴 (예: /LSW/flDownload.do?flSeq=…)
        return (f"{_BASE_URL}{link}" if link.startswith("/") else link), file_type
