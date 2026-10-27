"""RequestClient 인터페이스(fetch_raw·fetch_parsed·_send·_parse)와 요청 도구를 가짜 클라이언트로 검증한다."""

import httpx
import pytest

from app.clients.request import RequestClient


class _EchoClient(RequestClient[str, dict]):
    """요청 문자열을 q 파라미터로 보내고 JSON 본문을 dict로 돌려주는 가짜 클라이언트."""

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
