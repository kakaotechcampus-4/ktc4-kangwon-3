"""서버 상태 확인 라우터 테스트."""

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_생존_확인은_항상_UP을_반환한다(client):
    response = client.get("/api/ai/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_설정과_프롬프트가_정상이면_READY를_반환한다(client, monkeypatch):
    monkeypatch.setattr("app.routers.health.load_settings", lambda: None)

    response = client.get("/api/ai/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "READY"}


def test_설정_오류가_있으면_503과_원인을_반환한다(client, monkeypatch):
    def broken_settings():
        raise ConfigError("OPENAI_API_KEY가 없습니다.")

    monkeypatch.setattr("app.routers.health.load_settings", broken_settings)

    response = client.get("/api/ai/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert any(error.startswith("config:") for error in body["errors"])


def test_프롬프트_파일이_없으면_503과_누락된_프롬프트를_반환한다(client, monkeypatch):
    monkeypatch.setattr("app.routers.health.load_settings", lambda: None)

    def missing_selection(name: str) -> str:
        if name == "selection":
            raise FileNotFoundError(name)
        return "prompt"

    monkeypatch.setattr("app.routers.health.load_prompt", missing_selection)

    response = client.get("/api/ai/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["errors"] == ["prompt: selection.md 누락"]
