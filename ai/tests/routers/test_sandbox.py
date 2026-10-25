"""샌드박스 진단 라우터: 키 검사, 접수(202·429·422), 상태 조회(공개 진단서·질문·내부 결과, dev- 상품만)."""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.routers._dummy import DummyAssessmentPresenter, build_dummy_assessment
from app.routers.sandbox import get_assessment_presenter
from app.routers.diagnose import get_session_manager
from app.schemas.agent import ExtractionInput
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.sessions.manager import SessionManager
from app.sessions.job import JobDone, JobNeedsInput
from app.sessions.store import SessionStore

ROUTE = "/api/ai/v1/sandbox/diagnose"
KEY = "test-dev-api-key-0123456789abcdefgh"
HEADERS = {"X-Dev-Api-Key": KEY}
_BASE = {
    "api_key": "test-key", "base_url": "https://mlapi.run/example/v1",
    "embedding_model": "openai/text-embedding-3-small", "data_go_kr_key": "k", "safetykorea_key": "k",
    "law_oc": "oc", "internal_api_token": "test-internal-token-0123456789abcdef",
    "be_base_url": "http://be-server:8080", "database_url": "",
}


def _wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("조건을 기다리다 시간 초과")
        time.sleep(0.01)


@pytest.fixture
def gate() -> threading.Event:
    event = threading.Event()
    yield event
    event.set()


@pytest.fixture
def manager(gate):
    """관문이 열릴 때까지 진단이 끝나지 않는 세션 관리자. 개발용 상한은 1."""
    received: list[ExtractionInput] = []

    def job(job_input, context, progress):
        received.append(job_input.source)
        gate.wait(timeout=5)
        return JobDone(build_dummy_assessment(job_input.source.product_id))

    instance = SessionManager(SessionStore(), job, max_running=2, max_dev_inflight=1)
    instance.received = received
    yield instance
    # 붙잡힌 진단을 풀고 닫아야 종료가 관문 대기 시간만큼 늘지 않음
    gate.set()
    instance.shutdown(wait=True)


def _client(manager, *, enabled: bool = True, presenter=None) -> TestClient:
    settings = config.Settings(**_BASE, dev_api_enabled=enabled, dev_api_key=KEY if enabled else "")
    app.dependency_overrides[config.get_settings] = lambda: settings
    app.dependency_overrides[get_session_manager] = lambda: manager
    app.dependency_overrides[get_assessment_presenter] = lambda: presenter or DummyAssessmentPresenter()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _submit(client) -> dict:
    response = client.post(ROUTE, json={"textBlocks": ["무선 RC 보트 2.4GHz"]}, headers=HEADERS)
    assert response.status_code == 202, response.text
    return response.json()["data"]


def test_꺼져_있으면_접수도_조회도_404(manager):
    client = _client(manager, enabled=False)

    assert client.post(ROUTE, json={"textBlocks": ["x"]}, headers=HEADERS).status_code == 404
    assert client.get(f"{ROUTE}/dev-x", headers=HEADERS).status_code == 404
    assert manager.received == []


def test_키가_없으면_접수하지_않는다(manager):
    response = _client(manager).post(ROUTE, json={"textBlocks": ["x"]})

    assert (response.status_code, response.json()["code"]) == (401, "AI_UNAUTHORIZED")
    assert manager.received == []


def test_접수하면_dev_상품_ID와_실행_ID를_돌려주고_진단서_없이_실행한다(manager):
    data = _submit(_client(manager))

    assert data["productId"].startswith("dev-") and data["status"] == "accepted"
    session = manager.get(data["productId"])
    assert (session.context.run_id, session.context.diagnosis_id) == (data["runId"], None)
    _wait_until(lambda: manager.received)
    assert manager.received[0].text_blocks == ["무선 RC 보트 2.4GHz"]


def test_이미지_URL만_보내도_추출_입력으로_넘긴다(manager):
    urls = ["https://example.com/a.jpg", "data:image/png;base64,AAA"]
    response = _client(manager).post(ROUTE, json={"imageUrls": urls}, headers=HEADERS)

    assert response.status_code == 202, response.text
    _wait_until(lambda: manager.received)
    assert manager.received[0].image_urls == urls


def test_끝나면_공개_진단서와_내부_결과를_함께_조회한다(manager, gate):
    client = _client(manager)
    data = _submit(client)

    running = client.get(f"{ROUTE}/{data['productId']}", headers=HEADERS).json()["data"]
    assert running["status"] in ("accepted", "running") and running["assessment"] is None

    gate.set()
    _wait_until(lambda: manager.get(data["productId"]).status.value == "completed")
    done = client.get(f"{ROUTE}/{data['productId']}", headers=HEADERS).json()["data"]

    assert (done["status"], done["runId"]) == ("completed", data["runId"])
    # BE가 결과 콜백으로 받을 공개 진단서 (콜백과 같은 변환기)
    assert {review["toolName"] for review in done["assessment"]["toolReviews"]} >= {"ELECTRICAL", "RADIO"}
    # 디버깅용 내부 결과
    assert done["result"]["product"]["product_id"] == data["productId"]
    assert done["presentationError"] is None


def test_답변_대기면_질문을_돌려준다():
    def job(job_input, context, progress):
        result = build_dummy_assessment(job_input.source.product_id)
        return JobNeedsInput(result.model_copy(update={"termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
                                                       "verification_status": FinalVerificationStatus.INCOMPLETE}),
                             DummyAssessmentPresenter().questions(result))

    manager = SessionManager(SessionStore(), job)
    try:
        client = _client(manager)
        data = _submit(client)
        _wait_until(lambda: manager.get(data["productId"]).status.value == "awaiting_input")
        body = client.get(f"{ROUTE}/{data['productId']}", headers=HEADERS).json()["data"]
    finally:
        manager.shutdown(wait=True)

    assert (body["questionRound"], body["questions"][0]["questionKey"]) == (1, "battery_only")
    assert body["assessment"] is None


def test_공개_진단서_변환이_실패하면_원인을_보여준다(manager, gate):
    class _Broken(DummyAssessmentPresenter):
        def assessment(self, result):
            raise ValueError("미완료인데 안내가 없는 진단서")

    client = _client(manager, presenter=_Broken())
    data = _submit(client)
    gate.set()
    _wait_until(lambda: manager.get(data["productId"]).status.value == "completed")

    body = client.get(f"{ROUTE}/{data['productId']}", headers=HEADERS).json()["data"]

    assert body["presentationError"] == "ValueError: 미완료인데 안내가 없는 진단서"
    assert body["result"] is not None


def test_내부_결과의_외부_API_키는_가려서_보여준다():
    leaked = "근거 https://apis.data.go.kr/x?serviceKey=secret1&type=XML, https://www.law.go.kr/y?OC=secret2"

    def job(job_input, context, progress):
        return JobDone(build_dummy_assessment(job_input.source.product_id).model_copy(update={"summary": leaked}))

    manager = SessionManager(SessionStore(), job)
    try:
        client = _client(manager)
        data = _submit(client)
        _wait_until(lambda: manager.get(data["productId"]).status.value == "completed")
        body = client.get(f"{ROUTE}/{data['productId']}", headers=HEADERS).json()["data"]
    finally:
        manager.shutdown(wait=True)

    assert body["result"]["summary"] == (
        "근거 https://apis.data.go.kr/x?serviceKey=***&type=XML, https://www.law.go.kr/y?OC=***"
    )
    # 세션 원본은 그대로
    assert manager.get(data["productId"]).result.summary == leaked


def test_운영_상품이나_없는_상품은_조회할_수_없다(manager):
    manager.submit("d-1", [ExtractionInput(product_id="p-운영", text_blocks=["상품 설명"])])
    client = _client(manager)

    for product_id in ("p-운영", "dev-없는-상품"):
        response = client.get(f"{ROUTE}/{product_id}", headers=HEADERS)
        assert (response.status_code, response.json()["code"]) == (404, "AI_NOT_FOUND")


def test_개발용_상한을_넘으면_429(manager):
    client = _client(manager)
    _submit(client)

    response = client.post(ROUTE, json={"textBlocks": ["또 하나"]}, headers=HEADERS)

    assert (response.status_code, response.json()["code"]) == (429, "AI_QUEUE_FULL")


@pytest.mark.parametrize("body", [
    {}, {"textBlocks": [], "imageUrls": []}, {"productId": "p-1", "textBlocks": ["x"]},
    {"imagesBase64": ["https://example.com/a.jpg"]},
])
def test_입력이_없거나_정의하지_않은_필드를_보내면_422(manager, body):
    # 상품 ID는 서버가 발급. 옛 이름(imagesBase64) 등 정의하지 않은 필드는 받지 않음
    response = _client(manager).post(ROUTE, json=body, headers=HEADERS)

    assert response.status_code == 422
    assert manager.received == []
