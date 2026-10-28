"""RequestClient 인터페이스(fetch_raw·fetch_parsed·_send·_parse)와 요청 도구를 가짜 클라이언트로 검증한다."""

import contextlib
import importlib
import inspect
import pkgutil

import httpx
import pytest

import app.clients
from app.clients.request import RequestClient
from app.observability.measurements import ClientCall, measurement_sinks


class _EchoClient(RequestClient[str, dict]):
    """요청 문자열을 q 파라미터로 보내고 JSON 본문을 dict로 돌려주는 가짜 클라이언트."""

    API = "echo"

    def __init__(self):
        super().__init__(base_url="https://api.example.test")

    def _send(self, request: str) -> httpx.Response:
        return self._get("/items", params={"q": request})

    def _parse(self, raw: httpx.Response) -> dict:
        return self._parse_json(raw)


def _json(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"q": request.url.params["q"]})


def test_fetch_raw는_파싱_전_원문_응답을_돌려준다(wire):
    client = _EchoClient()
    wire(client, _json)

    raw = client.fetch_raw("전기")

    assert isinstance(raw, httpx.Response)
    assert raw.json() == {"q": "전기"}


def test_fetch_parsed는_send_결과를_parse에_넣은_값을_돌려준다(wire):
    client = _EchoClient()
    wire(client, _json)

    assert client.fetch_parsed("전기") == {"q": "전기"}


def test_send나_parse를_구현하지_않은_클라이언트는_만들_수_없다():
    class _NoParse(RequestClient[str, dict]):
        def _send(self, request):
            ...

    with pytest.raises(TypeError, match="_parse"):
        _NoParse(base_url="https://api.example.test")


def test_POST는_form_본문과_JSON_본문을_구분해_보낸다(wire):
    client = _EchoClient()
    sent = wire(client, lambda request: httpx.Response(200))

    client._post("/form", data={"srwr": "전기포트"})
    client._post("/json", json={"k": "v"})

    assert sent[0].headers["content-type"] == "application/x-www-form-urlencoded"
    assert sent[1].headers["content-type"] == "application/json"


@pytest.mark.parametrize("param", ["serviceKey", "OC"])
def test_HTTP_오류_메시지의_키_값은_가린다(wire, param):
    client = _EchoClient()
    wire(client, lambda request: httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client._get("/items", params={param: "secret-key", "type": "XML"})
    masked = RequestClient._mask_url(exc_info.value)

    assert "secret-key" not in str(masked)
    assert f"{param}=***" in str(masked)
    assert masked.response.status_code == 500


def test_키_이름이_들어간_다른_파라미터는_가리지_않는다(wire):
    client = _EchoClient()
    wire(client, lambda request: httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client._get("/items", params={"doc": "keep", "serviceKeyword": "keep2", "OC": "secret"})
    message = str(RequestClient._mask_url(exc_info.value))

    assert "doc=keep" in message and "serviceKeyword=keep2" in message and "OC=***" in message


@pytest.fixture
def calls():
    recorded: list[ClientCall] = []
    with measurement_sinks.added(recorded.append):
        yield recorded


def _raise(exc: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc
    return handler


@pytest.mark.parametrize(("handler", "expected"), [
    (_json, "ok"),
    (lambda request: httpx.Response(503), "http_error"),
    (_raise(httpx.ReadTimeout("느림")), "timeout"),
    (_raise(httpx.ConnectError("거부")), "connect_error"),
    (lambda request: httpx.Response(200, text="오류 안내 페이지"), "api_error"),
])
def test_조회마다_서버와_결과와_시간을_측정_기록으로_남긴다(wire, calls, handler, expected):
    client = _EchoClient()
    wire(client, handler)

    with contextlib.suppress(Exception):
        client.fetch_parsed("전기")

    [call] = calls
    assert (call.api, call.result) == ("echo", expected)
    assert call.seconds >= 0


def test_원문_조회는_해석하지_않아_HTTP_결과만_남긴다(wire, calls):
    client = _EchoClient()
    wire(client, lambda request: httpx.Response(200, text="오류 안내 페이지"))

    client.fetch_raw("전기")

    assert [call.result for call in calls] == ["ok"]


def test_오류를_돌려주는_클라이언트의_4xx도_HTTP_오류로_남긴다(wire, calls):
    class _NoRaise(_EchoClient):
        def _send(self, request: str) -> httpx.Response:
            return self._client.get("/items", params={"q": request})

    client = _NoRaise()
    wire(client, lambda request: httpx.Response(409, json={"q": "x"}))

    client.fetch_parsed("전기")

    assert [call.result for call in calls] == ["http_error"]


def test_클라이언트가_감싼_예외는_원인_예외로_결과를_정한다(wire, calls):
    class _Wrapping(_EchoClient):
        def _send(self, request: str) -> httpx.Response:
            try:
                return super()._send(request)
            except httpx.TransportError as exc:
                raise RuntimeError("전송 실패") from exc

    client = _Wrapping()
    wire(client, _raise(httpx.ReadTimeout("느림")))

    with pytest.raises(RuntimeError):
        client.fetch_parsed("전기")

    assert [call.result for call in calls] == ["timeout"]


def test_앱의_클라이언트는_모두_호출하는_서버_이름을_지정한다():
    for module in pkgutil.walk_packages(app.clients.__path__, "app.clients."):
        importlib.import_module(module.name)

    def concrete(cls):
        for sub in cls.__subclasses__():
            yield from concrete(sub)
            if not inspect.isabstract(sub) and sub.__module__.startswith("app.clients."):
                yield sub

    missing = sorted({cls.__qualname__ for cls in concrete(RequestClient) if cls.API == RequestClient.API})
    assert missing == []
