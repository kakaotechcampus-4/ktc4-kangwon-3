"""별표·첨부 원본 파일 내려받기 클라이언트의 요청 주소와 오류 응답 구분을 확인한다."""

import httpx
import pytest
from pydantic import ValidationError

from app.clients.law import AnnexFileClient
from app.schemas.clients.law_request import AnnexFileRequest

# 법제처 응답의 Content-Disposition (퍼센트 인코딩된 UTF-8 파일명)
_DISPOSITION = 'attachment; filename="%5B%EB%B3%84%ED%91%9C%201%5D%20%EC%84%B8%EB%B6%80%ED%92%88%EB%AA%A9.hwp"'


def _file(content: bytes = b"HWP Document File", disposition: str = _DISPOSITION):
    headers = {"content-type": "application/hwp;;charset=UTF-8", "content-disposition": disposition}
    return lambda request: httpx.Response(200, headers=headers, content=content)


def _html(body: str):
    return lambda request: httpx.Response(200, headers={"content-type": "text/html;charset=UTF-8"}, text=body)


@pytest.mark.parametrize("file_url", [
    "https://www.law.go.kr/LSW/flDownload.do?flSeq=169584877",
    "/LSW/flDownload.do?flSeq=169584877",
    # 첨부파일 링크 모양. http는 301로 돌아가 같은 다운로드 주소로 보냄
    "http://law.go.kr/flDownload.do?flSeq=169584877",
])
def test_링크_모양과_관계없이_같은_다운로드_주소로_요청한다(wire, file_url):
    client = AnnexFileClient()
    sent = wire(client, _file())

    client.fetch_parsed(AnnexFileRequest(file_url=file_url))

    assert str(sent[0].url) == "https://www.law.go.kr/LSW/flDownload.do?flSeq=169584877"


def test_파일명은_퍼센트_인코딩을_풀고_형식은_확장자로_정한다(wire):
    client = AnnexFileClient()
    wire(client, _file(content=b"\xd0\xcf\x11\xe0"))

    result = client.fetch_parsed(AnnexFileRequest(file_url="/LSW/flDownload.do?flSeq=1"))

    assert (result.file_name, result.file_type, result.content) == ("[별표 1] 세부품목.hwp", "hwp", b"\xd0\xcf\x11\xe0")


@pytest.mark.parametrize(("handler", "message"), [
    # 실제 응답: 없는 번호는 HTTP 200 + alert 스크립트, 잘못된 번호는 HTML 오류 페이지, 어떤 번호는 0바이트
    (_html("<script>alert(' 파일이 없습니다. '); </script>"), "해당 파일이 없습니다"),
    (_html("<!DOCTYPE html><html><body>오류</body></html>"), "파일이 아닌 응답"),
    (_file(content=b""), "빈 파일"),
    (_file(disposition=""), "첨부 파일명이 없습니다"),
])
def test_HTTP_200이어도_파일이_아니면_예외로_올린다(wire, handler, message):
    client = AnnexFileClient()
    wire(client, handler)

    with pytest.raises(RuntimeError, match=message):
        client.fetch_parsed(AnnexFileRequest(file_url="/LSW/flDownload.do?flSeq=1"))


@pytest.mark.parametrize("file_url", [
    "https://example.com/LSW/flDownload.do?flSeq=1",
    "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=1",
    "/LSW/flDownload.do?flSeq=abc",
])
def test_법제처_다운로드_링크가_아니면_요청하지_않는다(file_url):
    with pytest.raises(ValidationError):
        AnnexFileRequest(file_url=file_url)
