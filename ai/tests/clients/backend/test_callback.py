"""콜백 HTTP 전송부가 BE 수신 경로·헤더·본문으로 보내고 응답을 SendResult로 돌려주는지 확인한다.

가짜 BE는 httpx.MockTransport. 실제 네트워크 요청은 보내지 않는다.
"""

import json

import httpx
import pytest

from app.clients.backend import BackendCallbackClient, CallbackTransportError, SendResult
from app.schemas.callback import ProductProgressEvent, PublicPipelineStage

TOKEN = "test-internal-token-0123456789abcdef"


def _event(product_id: str = "01990000-0000-7000-8000-000000000001") -> ProductProgressEvent:
    return ProductProgressEvent(
        event_id="e-1", diagnosis_id="d-1", product_id=product_id, run_id="run-1", sequence=1,
        stage=PublicPipelineStage.EXTRACTION, stage_status="started",
    )


def _sender(handler, base_url: str = "http://be-server:8080") -> BackendCallbackClient:
    return BackendCallbackClient(base_url, TOKEN, transport=httpx.MockTransport(handler))


def test_BE_수신_경로로_토큰_헤더와_camelCase_본문을_보낸다():
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"code": "OK", "message": "", "data": None})

    result = _sender(handler).send(_event())

    [request] = requests
    assert (request.method, str(request.url)) == (
        "POST", "http://be-server:8080/internal/v1/ai/products/01990000-0000-7000-8000-000000000001")
    assert request.headers["X-Internal-Token"] == TOKEN
    body = json.loads(request.content)
    # 기본값인 eventType과 값이 없는 toolName도 빠지지 않음 (BE #329)
    assert body["eventType"] == "product_progress"
    assert body["toolName"] is None
    assert (body["productId"], body["runId"], body["stageStatus"]) == (
        "01990000-0000-7000-8000-000000000001", "run-1", "started")
    assert result == SendResult(200, "OK")


def test_BE_주소_끝의_슬래시는_경로에_겹치지_않는다():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200)

    _sender(handler, base_url="https://palgijeone.com/").send(_event("p-1"))

    assert urls == ["https://palgijeone.com/internal/v1/ai/products/p-1"]


def test_상품_ID는_경로_한_칸으로만_들어간다():
    paths = []

    def handler(request):
        paths.append(request.url.raw_path.decode())
        return httpx.Response(200)

    _sender(handler).send(_event("p/1"))

    assert paths == ["/internal/v1/ai/products/p%2F1"]


@pytest.mark.parametrize(("status", "body", "expected"), [
    (409, {"code": "COMMON-009", "message": "잠시 후 다시 시도", "data": None}, SendResult(409, "COMMON-009")),
    (401, {"code": "COMMON-004", "message": "인증 실패", "data": None}, SendResult(401, "COMMON-004")),
    (200, {"message": "code 없음"}, SendResult(200, None)),
    (200, ["목록"], SendResult(200, None)),
])
def test_응답_본문의_code를_SendResult에_담는다(status, body, expected):
    assert _sender(lambda request: httpx.Response(status, json=body)).send(_event()) == expected


def test_원문_조회는_4xx도_예외_없이_BE_응답을_그대로_돌려준다():
    raw = _sender(lambda request: httpx.Response(409, json={"code": "COMMON-010"})).fetch_raw(_event())

    assert (raw.status_code, raw.json()) == (409, {"code": "COMMON-010"})


def test_JSON이_아닌_응답은_code_없이_상태만_돌려준다():
    # nginx 502 같은 HTML 응답
    sender = _sender(lambda request: httpx.Response(502, text="<html>Bad Gateway</html>"))

    assert sender.send(_event()) == SendResult(502, None)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("시간 초과"), httpx.ConnectError("연결 거부")])
def test_응답을_받지_못하면_재시도_대상_오류로_바꾸고_토큰은_노출하지_않는다(error):
    def handler(request):
        raise error

    with pytest.raises(CallbackTransportError) as exc_info:
        _sender(handler).send(_event())

    assert TOKEN not in str(exc_info.value)
