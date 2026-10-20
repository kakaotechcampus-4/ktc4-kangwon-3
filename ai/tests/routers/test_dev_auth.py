"""개발용 진단 API 키 검사를 시험용 경로 하나로 확인한다."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config
from app.exception_handlers import register_exception_handlers
from app.routers import dev_auth
from app.routers.dev_auth import DEV_API_KEY_HEADER, require_dev_api_key

KEY = "test-dev-api-key-0123456789abcdefgh"
_BASE = {
    "api_key": "test-key", "base_url": "https://mlapi.run/example/v1",
    "embedding_model": "openai/text-embedding-3-small", "data_go_kr_key": "k", "safetykorea_key": "k",
    "law_oc": "oc", "internal_api_token": "test-internal-token-0123456789abcdef",
    "be_base_url": "http://be-server:8080", "database_url": "",
}


def _client(**settings) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/dev/ping", dependencies=[Depends(require_dev_api_key)])
    def ping():
        return {"ok": True}

    app.dependency_overrides[config.get_settings] = lambda: config.Settings(**{**_BASE, **settings})
    return TestClient(app)


def test_꺼져_있으면_키가_맞아도_경로가_없는_것처럼_404():
    response = _client().get("/dev/ping", headers={DEV_API_KEY_HEADER: KEY})

    assert (response.status_code, response.json()["code"]) == (404, "AI_NOT_FOUND")


@pytest.mark.parametrize("headers", [{}, {DEV_API_KEY_HEADER: ""}, {DEV_API_KEY_HEADER: KEY[:-1]},
                                     {DEV_API_KEY_HEADER: KEY + "x"},
                                     {DEV_API_KEY_HEADER: b"\xe9" * 34}])  # ASCII가 아닌 바이트
def test_키가_없거나_틀리면_401이고_키는_응답에_남기지_않는다(headers):
    response = _client(dev_api_enabled=True, dev_api_key=KEY).get("/dev/ping", headers=headers)

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert KEY not in response.text


def test_키가_맞으면_통과한다():
    response = _client(dev_api_enabled=True, dev_api_key=KEY).get("/dev/ping", headers={DEV_API_KEY_HEADER: KEY})

    assert (response.status_code, response.json()) == (200, {"ok": True})


def test_키는_상수_시간_비교로_검사한다(monkeypatch):
    # 앞부분이 맞을수록 빨리 끝나는 == 비교는 응답 시간으로 키를 한 글자씩 알아낼 수 있음
    calls = []
    original = dev_auth.hmac.compare_digest
    monkeypatch.setattr(dev_auth.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or original(a, b))

    _client(dev_api_enabled=True, dev_api_key=KEY).get("/dev/ping", headers={DEV_API_KEY_HEADER: "wrong"})

    assert calls == [(b"wrong", KEY.encode())]
