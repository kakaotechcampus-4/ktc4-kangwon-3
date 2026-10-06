"""진단 라우터 테스트. 파이프라인 연결 전이라 501을 반환하는 현재 동작을 확인한다."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("/api/ai/v1/diagnose/content", {"product_id": "p-1", "text_blocks": ["상품 설명"]}),
        ("/api/ai/v1/diagnose/url", {"product_id": "p-1", "source_url": "https://example.com/item"}),
    ],
)
def test_파이프라인_연결_전에는_501을_반환한다(client, route, payload):
    # 파이프라인 연결 시 실제 진단 결과 검증으로 교체
    response = client.post(route, json=payload)

    assert response.status_code == 501
    assert "구현되지 않았습니다" in response.json()["detail"]


def test_진단_요청도_스키마_검증은_먼저_수행한다(client):
    assert client.post("/api/ai/v1/diagnose/content", json={"product_id": "p-1"}).status_code == 422
