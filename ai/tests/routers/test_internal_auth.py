"""BE 내부 토큰 검사를 시험용 경로 하나로 확인한다."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, main
from app.routers import internal_auth
from app.routers.exception_handlers import register_exception_handlers
from app.routers.internal_auth import INTERNAL_TOKEN_HEADER, require_internal_token

TOKEN = "test-internal-token-0123456789abcdef"
_SETTINGS = config.Settings(
    api_key="test-key", base_url="https://mlapi.run/example/v1", embedding_model="openai/text-embedding-3-small",
    data_go_kr_key="k", safetykorea_key="k", law_oc="oc", internal_api_token=TOKEN,
    be_base_url="http://be-server:8080", database_url="",
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/internal/ping", dependencies=[Depends(require_internal_token)])
    def ping():
        return {"ok": True}

    app.dependency_overrides[config.get_settings] = lambda: _SETTINGS
    return TestClient(app)


@pytest.mark.parametrize("headers", [{}, {INTERNAL_TOKEN_HEADER: ""}, {INTERNAL_TOKEN_HEADER: TOKEN[:-1]},
                                     {INTERNAL_TOKEN_HEADER: TOKEN + "x"},
                                     {INTERNAL_TOKEN_HEADER: b"\xe9" * 36}])  # ASCII가 아닌 바이트
def test_토큰이_없거나_틀리면_401이고_토큰은_응답에_남기지_않는다(client, headers):
    response = client.get("/internal/ping", headers=headers)

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert TOKEN not in response.text


def test_토큰이_맞으면_통과한다(client):
    response = client.get("/internal/ping", headers={INTERNAL_TOKEN_HEADER: TOKEN})

    assert (response.status_code, response.json()) == (200, {"ok": True})


def test_토큰은_상수_시간_비교로_검사한다(client, monkeypatch):
    # 앞부분이 맞을수록 빨리 끝나는 == 비교는 응답 시간으로 토큰을 한 글자씩 알아낼 수 있음
    calls = []
    original = internal_auth.hmac.compare_digest
    monkeypatch.setattr(internal_auth.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or original(a, b))

    client.get("/internal/ping", headers={INTERNAL_TOKEN_HEADER: "wrong"})

    assert calls == [(b"wrong", TOKEN.encode())]


def test_Swagger에서_더미_경로는_내부_토큰_샌드박스는_개발용_키로_보인다():
    # 보안 방식 이름이 같으면 하나로 합쳐져 Authorize로 넣은 값이 엉뚱한 헤더로 나감
    spec = main.app.openapi()
    schemes = {name: scheme["name"] for name, scheme in spec["components"]["securitySchemes"].items()}
    used = {path: {schemes[name] for item in op.get("security", []) for name in item}
            for path, ops in spec["paths"].items() for op in ops.values()}

    assert used["/api/ai/v1/dummy/diagnose/content"] == {INTERNAL_TOKEN_HEADER}
    assert used["/api/ai/v1/dummy/diagnose/resume"] == {INTERNAL_TOKEN_HEADER}
    assert used["/api/ai/v1/diagnose/content"] == set()
    assert used["/api/ai/v1/sandbox/diagnose"] == {"X-Dev-Api-Key"}
    assert used["/api/ai/v1/health"] == set()
