"""관세청 CLIP 국내 품목분류 결정사례 상세 클라이언트.

역할
    검색 응답의 설명·결정이유는 검색어 주변 발췌라, 웹 화면이 쓰는 상세 조회로 전문을 받음.
    결과는 검색 항목과 같은 CLIPCase라 DB 적재·검색이 같은 모양을 씀.
"""

import html
import re
from urllib.parse import parse_qs

import httpx

from ..request import RequestClient
from .clip import parse_hs_codes
from ...schemas.clients.customs_request import CLIPDetailRequest
from ...schemas.clients.customs_response import CLIPCase

# 상세 표의 한 줄: <th>항목</th> <td>값</td>
_ROW_RE = re.compile(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", re.S)
_FIELDS = {"품명": "product_name", "물품설명": "description", "결정사유": "decision_reason"}


class CLIPDetailClient(RequestClient[CLIPDetailRequest, CLIPCase]):
    """CLIP 국내 품목분류 결정사례 상세 클라이언트.

    방식 : POST/form
    서비스 키 : 불필요
    비고
        응답은 HTML 표. 없는 문서 ID도 200과 빈 표로 옴.
        시행일자·결정세번은 hidden input(txtEnfrDt·txtDtrmHsSgn)에 기호 없는 값이 따로 있음.
    """

    _ENDPOINT = "/clip/prlstclsfsrch/retrieveDmstPrlstClsfCaseDtl.do"

    def __init__(self):
        super().__init__(base_url="https://unipass.customs.go.kr", timeout=30.0)

    def _send(self, request: CLIPDetailRequest) -> httpx.Response:
        """결정사례 상세 조회를 요청한다.

        Args:
            request: 상세 조회 요청 파라미터.

        Returns:
            httpx.Response: HTML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        return self._post(self._ENDPOINT, data={"rrdcNo": request.doc_id})

    def _parse(self, raw: httpx.Response) -> CLIPCase:
        """결정사례 상세 HTML을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 HTML 원문 응답.

        Returns:
            CLIPCase: 설명·결정이유가 전문인 결정사례.

        Raises:
            RuntimeError: 상세 표가 비어 있는 경우(없는 문서 ID).
        """
        page = raw.text
        values = {}
        for header, cell in _ROW_RE.findall(page):
            field = _FIELDS.get(re.sub(r"<[^>]+>|\s", "", header))
            if field:
                values[field] = self._cell_text(cell)
        # 품명만 있고 설명·결정사유가 빈 사례도 있음 (2026-10-25 전체 적재 중 2건)
        if not any(values.values()):
            raise RuntimeError("CLIP 결정사례 상세가 비어 있습니다 (없는 문서 ID).")
        return CLIPCase(
            hs_codes=parse_hs_codes(self._hidden(page, "txtDtrmHsSgn")),  # 결정 HS 코드 목록
            product_name=values.get("product_name", ""),                  # 물품명
            description=values.get("description", ""),                    # 물품설명 전문
            decision_reason=values.get("decision_reason", ""),            # 결정 이유 전문
            # 응답 HTML엔 문서 ID가 없어 요청 본문에서 꺼냄
            doc_id=parse_qs(raw.request.content.decode())["rrdcNo"][0],
            enforce_date=self._hidden(page, "txtEnfrDt") or None,         # 시행일자 (YYYYMMDD)
        )

    @staticmethod
    def _hidden(page: str, name: str) -> str:
        """hidden input 값을 꺼낸다.

        Args:
            page: 상세 HTML.
            name: input 이름.

        Returns:
            str: 값. 없으면 빈 문자열.
        """
        match = re.search(rf'name="{name}"\s+value="([^"]*)"', page)
        return html.unescape(match.group(1)) if match else ""

    @staticmethod
    def _cell_text(cell: str) -> str:
        """표 칸의 글자만 남긴다. 줄바꿈(<br>)은 살리고 줄 안 공백은 하나로 모음.

        Args:
            cell: <td> 안 HTML.

        Returns:
            str: 정리된 글자.
        """
        cell = re.sub(r"<br\s*/?>", "\n", cell, flags=re.I)
        cell = html.unescape(re.sub(r"<[^>]+>", " ", cell))
        lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in cell.splitlines()]
        return "\n".join(line for line in lines if line)
