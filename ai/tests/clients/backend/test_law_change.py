"""법령 변경 전송부가 BE 수신 경로·헤더·본문으로 보내고 응답을 SendResult로 돌려주는지 확인한다.

가짜 BE는 httpx.MockTransport. 실제 네트워크 요청은 보내지 않는다.
"""

import json
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from app.clients.backend import BackendLawChangeClient, CallbackTransportError, SendResult
from app.schemas.callback import LawChangeCallbackRequest, PublicLawChangeDto

TOKEN = "test-internal-token-0123456789abcdef"


def _change(**overrides) -> PublicLawChangeDto:
    fields = {
        "law_name": "어린이제품 안전 특별법 시행규칙", "document_id": "012345", "admrul": False, "tool_name": "CHILDREN",
        "serial_number": "291321", "previous_serial_number": "280000", "revision_type": "일부개정",
        "enforce_date": date(2026, 10, 20), "issued_date": date(2026, 4, 20),
    }
    return PublicLawChangeDto(**{**fields, **overrides})


def _request(*changes: PublicLawChangeDto) -> LawChangeCallbackRequest:
    return LawChangeCallbackRequest(changes=list(changes) or [_change()])


def _client(handler) -> BackendLawChangeClient:
    return BackendLawChangeClient("http://be-server:8080/", TOKEN, transport=httpx.MockTransport(handler))


def test_BE_수신_경로로_토큰_헤더와_약속한_본문을_보낸다():
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"code": "OK", "message": "", "data": None})

    result = _client(handler).send(_request())

    [request] = requests
    assert (request.method, str(request.url)) == ("POST", "http://be-server:8080/internal/v1/ai/law-changes")
    assert request.headers["X-Internal-Token"] == TOKEN
    assert json.loads(request.content) == {
        "changes": [{
            "lawName": "어린이제품 안전 특별법 시행규칙", "documentId": "012345", "admrul": False,
            "toolName": "CHILDREN", "serialNumber": "291321", "previousSerialNumber": "280000",
            "revisionType": "일부개정", "enforceDate": "2026-10-20", "issuedDate": "2026-04-20",
        }],
    }
    assert result == SendResult(200, "OK")


def test_값이_없는_선택_필드는_null로_보낸다():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200)

    change = _change(previous_serial_number=None, revision_type=None, enforce_date=None, issued_date=None)
    _client(handler).send(_request(change))

    sent = bodies[0]["changes"][0]
    assert (sent["previousSerialNumber"], sent["revisionType"], sent["enforceDate"], sent["issuedDate"]) == (
        None, None, None, None)


def test_거절_응답도_예외_없이_상태와_code를_돌려준다():
    client = _client(lambda request: httpx.Response(409, json={"code": "COMMON-003", "message": "겹침", "data": None}))

    assert client.send(_request()) == SendResult(409, "COMMON-003")


@pytest.mark.parametrize("error", [httpx.ReadTimeout("시간 초과"), httpx.ConnectError("연결 거부")])
def test_응답을_받지_못하면_재시도_대상_오류로_바꾸고_토큰은_노출하지_않는다(error):
    def handler(request):
        raise error

    with pytest.raises(CallbackTransportError) as exc_info:
        _client(handler).send(_request())

    assert TOKEN not in str(exc_info.value)


def test_빈_묶음은_만들_수_없다():
    # BE @NotEmpty와 같은 조건
    with pytest.raises(ValidationError):
        LawChangeCallbackRequest(changes=[])


@pytest.mark.parametrize("field", ["law_name", "document_id", "serial_number"])
def test_필수_문자열이_공백뿐이면_만들_수_없다(field):
    # BE @NotBlank와 같은 조건
    with pytest.raises(ValidationError):
        _change(**{field: "  "})


def test_BE에_없는_분야_이름은_만들_수_없다():
    with pytest.raises(ValidationError):
        _change(tool_name="children_product_safety")
