"""HTTP 요청 미들웨어가 라우트 템플릿·상태 코드·처리 시간을 측정 기록으로 남기는지 확인한다."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.observability.http_requests import record_http_requests
from app.observability.measurements import measurement_sinks


@pytest.fixture
def client():
    app = FastAPI()
    app.middleware("http")(record_http_requests)

    @app.get("/items/{item_id}")
    def item(item_id: int):
        return {"id": item_id}

    @app.get("/broken")
    def broken():
        raise RuntimeError("처리 실패")

    @app.get("/metrics")
    def metrics():
        return {}

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return JSONResponse({"code": "AI_INTERNAL_ERROR"}, status_code=500)

    return TestClient(app, raise_server_exceptions=False)


def _requests(client, *paths):
    records = []
    with measurement_sinks.added(records.append):
        for path in paths:
            client.get(path)
    return records


def test_원래_경로가_아니라_라우트_템플릿으로_남긴다(client):
    records = _requests(client, "/items/1", "/items/2", "/items/abc")

    assert [(r.route, r.method, r.status) for r in records] == [
        ("/items/{item_id}", "GET", 200), ("/items/{item_id}", "GET", 200), ("/items/{item_id}", "GET", 422)]
    assert all(r.seconds >= 0 for r in records)


def test_맞는_라우트가_없으면_unmatched로_남긴다(client):
    [record] = _requests(client, "/no/such/path")

    assert (record.route, record.status) == ("unmatched", 404)


def test_처리_중_예외는_500으로_남긴다(client):
    [record] = _requests(client, "/broken")

    assert (record.route, record.status) == ("/broken", 500)


def test_지표_수집_요청은_남기지_않는다(client):
    assert _requests(client, "/metrics") == []
