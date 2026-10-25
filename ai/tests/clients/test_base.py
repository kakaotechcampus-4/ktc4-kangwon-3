"""외부 통신 클라이언트 공통 베이스(연결)와 공통 도구(키 가리기)를 검증한다."""

import httpx

from app.clients.base import BaseClient, mask_sensitive_params


def test_만들_때_넘긴_전송_계층으로_요청을_보낸다():
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    client = BaseClient(base_url="https://api.example.test", headers={"X-Test": "1"},
                        transport=httpx.MockTransport(record))
    client._client.get("/items")
    client.close()

    assert str(sent[0].url) == "https://api.example.test/items"
    assert sent[0].headers["X-Test"] == "1"


def test_mask_sensitive_params는_키_값만_대소문자_구분_없이_가린다():
    text = '근거 "https://x.kr/a?ServiceKey=k1&type=XML&oc=k2" 참고, serviceKey=k3'

    masked = mask_sensitive_params(text)

    assert masked == '근거 "https://x.kr/a?ServiceKey=***&type=XML&oc=***" 참고, serviceKey=k3'
