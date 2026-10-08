"""진단 라우터 테스트. 진단서 단위 접수(202·409·429·422)와 URL 진단 501을 확인한다."""

from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability.context import PipelineStage
from app.routers import _dummy
from app.routers._dummy import build_dummy_assessment, run_dummy_diagnosis
from app.routers.diagnose import get_session_executor
from app.schemas.agent import ExtractionInput
from app.schemas.session import SessionStatus
from app.sessions.executor import SessionExecutor
from app.sessions.store import SessionStore

CONTENT = "/api/ai/v1/diagnose/content"


def _payload(*product_ids: str, diagnosis_id: str = "d-1") -> dict:
    return {
        "diagnosisId": diagnosis_id,
        "products": [{"productId": pid, "textBlocks": ["상품 설명"]} for pid in product_ids],
    }


@pytest.fixture
def gate() -> Event:
    """진단 함수를 붙잡아 두는 관문. 테스트 끝에 열어 스레드를 풀어줌."""
    event = Event()
    yield event
    event.set()


@pytest.fixture
def executor(gate):
    """lifespan 대신 쓰는 실행기. 관문이 열릴 때까지 진단이 끝나지 않음."""
    received: list[ExtractionInput] = []

    def job(item, context, progress):
        received.append(item)
        gate.wait(timeout=5)
        return build_dummy_assessment(item.product_id)

    instance = SessionExecutor(SessionStore(), job, max_running=2, max_inflight=3)
    instance.received = received
    yield instance
    instance.shutdown(wait=True)


@pytest.fixture
def client(executor) -> TestClient:
    app.dependency_overrides[get_session_executor] = lambda: executor
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_상품별_세션을_만들고_202를_반환한다(client, executor):
    response = client.post(CONTENT, json=_payload("p-1", "p-2"))

    assert response.status_code == 202
    assert response.json() == {
        "code": "OK",
        "message": "진단 요청이 접수되었습니다.",
        "details": None,
        "data": {"diagnosisId": "d-1", "acceptedProductIds": ["p-1", "p-2"]},
    }
    sessions = [executor.store.get(pid) for pid in ("p-1", "p-2")]
    assert all(s.context.diagnosis_id == "d-1" for s in sessions)
    assert all(s.status in (SessionStatus.ACCEPTED, SessionStatus.RUNNING) for s in sessions)


def test_이미지는_추출_입력의_image_urls로_넘긴다(client, executor, gate):
    product = {"productId": "p-1", "imagesBase64": ["data:image/png;base64,AAA"], "sourceUrl": "https://example.com/1"}

    client.post(CONTENT, json={"diagnosisId": "d-1", "products": [product]})
    gate.set()
    executor.shutdown(wait=True)

    assert executor.received == [ExtractionInput(
        product_id="p-1", source_url="https://example.com/1", image_urls=["data:image/png;base64,AAA"],
    )]


def test_진행_중인_상품이_섞이면_전체를_409로_거절한다(client, executor):
    client.post(CONTENT, json=_payload("p-1"))

    response = client.post(CONTENT, json=_payload("p-1", "p-2", diagnosis_id="d-2"))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "AI_SESSION_CONFLICT"
    assert body["data"] == {"conflictProductIds": ["p-1"]}
    assert executor.store.get("p-2") is None


def test_대기열이_가득_차면_429를_반환한다(client, executor):
    client.post(CONTENT, json=_payload("p-1", "p-2"))

    response = client.post(CONTENT, json=_payload("p-3", "p-4", diagnosis_id="d-2"))

    assert response.status_code == 429
    assert response.json()["code"] == "AI_QUEUE_FULL"
    assert executor.store.get("p-3") is None


@pytest.mark.parametrize("payload", [
    {"product_id": "p-1", "text_blocks": ["상품 설명"]},
    {"diagnosisId": "d-1", "products": []},
    {"diagnosisId": "d-1", "products": [{"productId": "p-1"}]},
])
def test_형식이_틀린_요청은_422로_거절하고_접수하지_않는다(client, executor, payload):
    assert client.post(CONTENT, json=payload).status_code == 422
    assert executor.store.unfinished() == []


def test_URL_진단은_아직_501을_반환한다(client):
    response = client.post("/api/ai/v1/diagnose/url", json={"product_id": "p-1", "source_url": "https://example.com/item"})

    assert response.status_code == 501
    assert "구현되지 않았습니다" in response.json()["detail"]


def test_더미_진단은_단계를_순서대로_알리고_고정_결과를_반환한다(monkeypatch):
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    stages: list[PipelineStage] = []

    class Recorder:
        def stage(self, stage):
            stages.append(stage)

    result = run_dummy_diagnosis(ExtractionInput(product_id="p-1", text_blocks=["설명"]), None, Recorder())

    assert stages == list(_dummy.DUMMY_STAGES)
    assert result.product.product_id == "p-1"
