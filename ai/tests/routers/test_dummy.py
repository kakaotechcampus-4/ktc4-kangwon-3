"""BE 연동 테스트용 더미 진단 라우터 테스트."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

CONTENT_ROUTE = "/api/ai/v1/dummy/diagnose/content"
URL_ROUTE = "/api/ai/v1/dummy/diagnose/url"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_텍스트_진단은_요청한_상품_ID로_고정_결과를_반환한다(client):
    response = client.post(CONTENT_ROUTE, json={"product_id": "p-1", "text_blocks": ["상품 설명"]})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OK"
    assert body["data"]["product"]["product_id"] == "p-1"


def test_URL_진단은_요청한_상품_ID로_고정_결과를_반환한다(client):
    response = client.post(URL_ROUTE, json={"product_id": "p-2", "source_url": "https://example.com/item"})

    assert response.status_code == 200
    assert response.json()["data"]["product"]["product_id"] == "p-2"


@pytest.mark.parametrize(
    "payload",
    [
        {"product_id": "p-1"},                                           # 텍스트·이미지 모두 없음
        {"product_id": "", "text_blocks": ["상품 설명"]},                 # 빈 상품 ID
        {"product_id": "p-1", "text_blocks": ["상품 설명"], "extra": 1},  # 정의되지 않은 필드
    ],
)
def test_텍스트_진단의_잘못된_요청은_422를_반환한다(client, payload):
    assert client.post(CONTENT_ROUTE, json=payload).status_code == 422


def test_URL_진단은_URL이_없으면_422를_반환한다(client):
    assert client.post(URL_ROUTE, json={"product_id": "p-2"}).status_code == 422
