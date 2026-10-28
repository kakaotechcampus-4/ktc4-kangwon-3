"""법제처 별표·첨부 원본 파일 내려받기 클라이언트.

역할
    본문 조회(law·admrul) 응답의 별표·첨부 파일 링크로 원본 파일(HWP·HWPX·PDF 등)을 받음.
    별표 표는 원본 파일에 칸 주소·병합이 그대로 있어, 본문의 별표내용(글자 그림 표)보다 정확히 복원됨.

주의
    파일 링크는 본문 조회 응답의 것을 씀. licbyl·admbyl 검색 결과의 링크는 별표 재업로드를 늦게 반영해
    옛 파일을 가리킬 수 있음 (korean-law-mcp annex-canonical, MIT).
    OC 없이 받는 공개 다운로드. 실패해도 HTTP 200으로 와서 응답 내용으로 오류를 가림.
"""

import re
from urllib.parse import unquote

import httpx

from ..request import RequestClient
from ...schemas.clients.law_request import AnnexFileRequest
from ...schemas.clients.law_response import AnnexFileResponse

_BASE_URL = "https://www.law.go.kr"
_DOWNLOAD_PATH = "/LSW/flDownload.do"
_FILE_SEQ_RE = re.compile(r"flSeq=(\d+)")
# filename*=UTF-8''… 또는 filename="…" (퍼센트 인코딩된 UTF-8)
_FILENAME_RE = re.compile(r"filename\*=(?:UTF-8'')?([^;]+)|filename=\"?([^\";]+)\"?", re.IGNORECASE)


class AnnexFileClient(RequestClient[AnnexFileRequest, AnnexFileResponse]):
    """별표·첨부 원본 파일 내려받기 클라이언트.

    Args:
        timeout: 요청 제한 시간(초). 큰 별표 파일이 있어 기본 30초.
    """

    API = "law"

    def __init__(self, timeout: float = 30.0):
        super().__init__(base_url=_BASE_URL, timeout=timeout)

    def _send(self, request: AnnexFileRequest) -> httpx.Response:
        """파일 번호(flSeq)로 다운로드 주소에 요청한다.

        링크 모양(http://law.go.kr/…, /LSW/…)과 관계없이 같은 주소로 보냄. http 링크는 301로 돌아가기 때문.

        Args:
            request: 내려받기 요청.

        Returns:
            httpx.Response: 원문 응답 (파일 바이트 또는 오류 HTML).

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답 시.
        """
        file_seq = _FILE_SEQ_RE.search(request.file_url).group(1)
        return self._get(_DOWNLOAD_PATH, params={"flSeq": file_seq})

    def _parse(self, raw: httpx.Response) -> AnnexFileResponse:
        """다운로드 응답을 파일명·형식·바이트로 바꾼다.

        Args:
            raw: `_send`가 받은 원문 응답.

        Returns:
            AnnexFileResponse: 원본 파일.

        Raises:
            RuntimeError: 파일이 없거나(HTML 응답), 첨부 파일명이 없거나, 빈 파일인 경우.
        """
        content_type = raw.headers.get("content-type", "")
        if content_type.startswith("text/html"):
            if "파일이 없습니다" in raw.text:
                raise RuntimeError("법제처에 해당 파일이 없습니다.")
            raise RuntimeError("파일이 아닌 응답을 받았습니다.")
        match = _FILENAME_RE.search(raw.headers.get("content-disposition", ""))
        if match is None:
            raise RuntimeError("응답에 첨부 파일명이 없습니다.")
        if not raw.content:
            raise RuntimeError("빈 파일을 받았습니다.")
        file_name = unquote(match.group(1) or match.group(2)).strip()
        file_type = file_name.rsplit(".", 1)[1].lower() if "." in file_name else None
        return AnnexFileResponse(file_name=file_name, file_type=file_type, content=raw.content)
