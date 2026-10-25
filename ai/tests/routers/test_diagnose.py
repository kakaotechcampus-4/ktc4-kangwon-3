"""진단 라우터 테스트. 진단서 단위 접수(202·409·429·422), 재진단(202·400·404·409·429·422), /diagnose 501을 확인한다.

/diagnose는 실제 파이프라인 연결 전까지 501이라, 접수·재진단 처리는 같은 처리를 쓰는 더미 경로로 확인함.
"""

from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.routers import _dummy
from app.routers._dummy import build_dummy_assessment, run_dummy_diagnosis
from app.routers.diagnose import get_session_manager, to_extraction_input
from app.schemas.agent import ExtractionInput
from app.schemas.base import utc_now
from app.schemas.callback import PublicQuestionDto
from app.schemas.request import DiagnosisProductInput
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.schemas.session import DiagnosisInput, DiagnosisSession, SessionStatus
from app.sessions.job import JobDone
from app.sessions.manager import SessionManager
from app.sessions.transitions import AskUser, Start, apply
from app.sessions.store import SessionStore

CONTENT = "/api/ai/v1/dummy/diagnose/content"
PRODUCTION_CONTENT = "/api/ai/v1/diagnose/content"


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
def manager(gate):
    """lifespan 대신 쓰는 세션 관리자. 관문이 열릴 때까지 진단이 끝나지 않음."""
    received: list[ExtractionInput] = []

    def job(job_input, context, progress):
        received.append(job_input.source)
        gate.wait(timeout=5)
        return JobDone(build_dummy_assessment(job_input.source.product_id))

    store = SessionStore()
    instance = SessionManager(store, job, max_running=2, max_inflight=3)
    instance.store = store
    instance.received = received
    yield instance
    # 관문을 먼저 열어야 붙잡힌 진단이 끝남. 안 열면 진단마다 5초 대기 후 종료
    gate.set()
    instance.shutdown(wait=True)


@pytest.fixture
def client(manager) -> TestClient:
    app.dependency_overrides[get_session_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_상품별_세션을_만들고_202를_반환한다(client, manager):
    response = client.post(CONTENT, json=_payload("p-1", "p-2"))

    assert response.status_code == 202
    sessions = [manager.get(pid) for pid in ("p-1", "p-2")]
    # 상품별 runId는 그 세션의 실행 ID. 이 실행의 콜백에 같은 값이 실림 (#310)
    assert response.json() == {
        "code": "OK",
        "message": "진단 요청이 접수되었습니다.",
        "details": None,
        "data": {"diagnosisId": "d-1", "products": [
            {"productId": s.context.product_id, "runId": s.context.run_id, "status": "accepted"} for s in sessions
        ]},
    }
    assert len({s.context.run_id for s in sessions}) == 2
    assert all(s.context.diagnosis_id == "d-1" for s in sessions)
    assert all(s.status in (SessionStatus.ACCEPTED, SessionStatus.RUNNING) for s in sessions)


def test_이미지는_추출_입력의_image_urls로_넘긴다():
    product = DiagnosisProductInput.model_validate(
        {"productId": "p-1", "imageUrls": ["data:image/png;base64,AAA"], "sourceUrl": "https://example.com/1"},
    )

    assert to_extraction_input(product) == ExtractionInput(
        product_id="p-1", source_url="https://example.com/1", image_urls=["data:image/png;base64,AAA"],
    )


def test_진행_중인_상품이_섞이면_전체를_409로_거절한다(client, manager):
    client.post(CONTENT, json=_payload("p-1"))

    response = client.post(CONTENT, json=_payload("p-1", "p-2", diagnosis_id="d-2"))

    assert response.status_code == 409
    assert response.json() == {
        "code": "AI_SESSION_CONFLICT",
        "message": "이미 진행 중인 상품이 있습니다.",
        "details": None,
        "data": {"conflictProductIds": ["p-1"]},
    }
    assert manager.get("p-2") is None


def test_대기열이_가득_차면_429를_반환한다(client, manager):
    client.post(CONTENT, json=_payload("p-1", "p-2"))

    response = client.post(CONTENT, json=_payload("p-3", "p-4", diagnosis_id="d-2"))

    assert response.status_code == 429
    assert response.json() == {
        "code": "AI_QUEUE_FULL",
        "message": "진단 대기열이 가득 찼습니다. 잠시 후 다시 요청해 주세요.",
        "details": None,
        "data": None,
    }
    assert manager.get("p-3") is None


@pytest.mark.parametrize("payload", [
    {"diagnosis_id": "d-1", "products": [{"product_id": "p-1", "text_blocks": ["상품 설명"]}]},
    {"diagnosisId": "d-1", "products": []},
    {"diagnosisId": "d-1", "products": [{"productId": "p-1"}]},
])
def test_형식이_틀린_요청은_422로_거절하고_접수하지_않는다(client, manager, payload):
    response = client.post(CONTENT, json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "AI_INVALID_REQUEST"
    assert response.json()["details"]
    assert manager.get("p-1") is None


def test_실제_진단_접수는_파이프라인_연결_전까지_501이고_접수하지_않는다(client, manager):
    response = client.post(PRODUCTION_CONTENT, json=_payload("p-1"))

    assert (response.status_code, response.json()["code"]) == (501, "AI_NOT_IMPLEMENTED")
    assert manager.get("p-1") is None


def test_실제_진단도_형식이_틀리면_501보다_422가_먼저다(client):
    response = client.post(PRODUCTION_CONTENT, json={"diagnosisId": "d-1", "products": []})

    assert (response.status_code, response.json()["code"]) == (422, "AI_INVALID_REQUEST")


def test_URL_진단_경로는_없다(client):
    # URL은 /diagnose/content의 sourceUrl로 받음 (#371)
    response = client.post("/api/ai/v1/diagnose/url", json={"productId": "p-1", "sourceUrl": "https://example.com/1"})

    assert response.status_code == 404


def test_더미_진단은_단계를_순서대로_알리고_고정_결과를_반환한다(monkeypatch):
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    stages: list[PipelineStage] = []

    class Recorder:
        def stage(self, stage):
            stages.append(stage)

    job_input = DiagnosisInput(source=ExtractionInput(product_id="p-1", text_blocks=["설명"]))

    outcome = run_dummy_diagnosis(job_input, None, Recorder())

    assert stages == list(_dummy.DUMMY_STAGES)
    assert isinstance(outcome, JobDone)
    assert outcome.result.product.product_id == "p-1"


RESUME = "/api/ai/v1/dummy/diagnose/resume"
PRODUCTION_RESUME = "/api/ai/v1/diagnose/resume"
_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


def _waiting(manager: SessionManager, product_id: str = "p-1", questions=_QUESTIONS):
    """질문으로 끝나 답변을 기다리는 세션. 관리자를 거치지 않고 전이표로 만들어 저장소에 직접 넣음."""
    now = utc_now()
    context = ExecutionContext.start(product_id=product_id, run_type=RunType.DUMMY, diagnosis_id="d-1")
    source = ExtractionInput(product_id=product_id, text_blocks=["상품 설명"])
    session = apply(DiagnosisSession(context=context, source=source), Start(), now=now).session
    awaiting = build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })
    waiting = apply(session, AskUser(awaiting, questions), now=now).session
    manager.store.add([waiting])
    return waiting


def _resume_payload(waiting, **fields) -> dict:
    return {
        "diagnosisId": "d-1", "productId": waiting.context.product_id, "runId": waiting.context.run_id,
        "questionRound": waiting.question_round, "answers": [{"questionKey": "battery_only", "answerText": "네"}],
        **fields,
    }


def test_답변_대기_상품을_새_runId로_재접수하고_202를_반환한다(client, manager):
    waiting = _waiting(manager)

    response = client.post(RESUME, json=_resume_payload(waiting))

    assert response.status_code == 202
    session = manager.get("p-1")
    assert response.json() == {
        "code": "OK",
        "message": "재진단 요청이 접수되었습니다.",
        "details": None,
        "data": {"productId": "p-1", "runId": session.context.run_id, "status": "accepted"},
    }
    assert session.context.run_id != waiting.context.run_id
    assert [(a.question_key, a.answer_text) for a in session.answers] == [("battery_only", "네")]


def test_실제_재진단은_파이프라인_연결_전까지_501이고_세션을_바꾸지_않는다(client, manager):
    waiting = _waiting(manager)

    response = client.post(PRODUCTION_RESUME, json=_resume_payload(waiting))

    assert (response.status_code, response.json()["code"]) == (501, "AI_NOT_IMPLEMENTED")
    assert manager.get("p-1") == waiting


def test_세션이_없으면_404를_반환한다(client):
    payload = {"diagnosisId": "d-1", "productId": "p-1", "runId": "run-1", "questionRound": 1,
               "answers": [{"questionKey": "battery_only", "answerText": "네"}]}

    response = client.post(RESUME, json=payload)

    assert response.status_code == 404
    assert response.json()["code"] == "AI_SESSION_NOT_FOUND"


@pytest.mark.parametrize("fields", [{"runId": "other-run"}, {"questionRound": 2}, {"diagnosisId": "d-2"}])
def test_기다리는_질문과_다른_답변은_409로_거절한다(client, manager, fields):
    waiting = _waiting(manager)

    response = client.post(RESUME, json=_resume_payload(waiting, **fields))

    assert response.status_code == 409
    assert response.json()["code"] == "AI_RESUME_CONFLICT"
    assert manager.get("p-1") == waiting


def test_같은_답변이_두_번_오면_두_번째는_409이고_실행은_하나만_생긴다(client, manager):
    waiting = _waiting(manager)
    first = client.post(RESUME, json=_resume_payload(waiting))

    second = client.post(RESUME, json=_resume_payload(waiting))

    assert (first.status_code, second.status_code) == (202, 409)
    assert manager.get("p-1").context.run_id == first.json()["data"]["runId"]


def test_묻지_않은_질문의_답변은_400과_질문_키로_거절한다(client, manager):
    waiting = _waiting(manager)
    answers = [{"questionKey": "battery_only", "answerText": "네"}, {"questionKey": "target_age", "answerText": "8세"}]

    response = client.post(RESUME, json=_resume_payload(waiting, answers=answers))

    assert response.status_code == 400
    assert response.json()["code"] == "AI_UNKNOWN_QUESTION_KEY"
    assert response.json()["data"] == {"questionKeys": ["target_age"]}
    assert manager.get("p-1") == waiting


def test_이번_회차_질문에_모두_답하지_않으면_422로_거절한다(client, manager):
    questions = [*_QUESTIONS, PublicQuestionDto(question_key="target_age", question_order=2, question_text="몇 세용인가요?")]
    waiting = _waiting(manager, questions=questions)

    response = client.post(RESUME, json=_resume_payload(waiting))

    assert (response.status_code, response.json()["code"]) == (422, "AI_INVALID_REQUEST")
    assert manager.get("p-1") == waiting


def test_재진단도_대기열이_가득_차면_429를_반환한다(client, manager):
    waiting = _waiting(manager)
    client.post(CONTENT, json=_payload("p-2", "p-3", "p-4"))

    response = client.post(RESUME, json=_resume_payload(waiting))

    assert response.status_code == 429
    assert manager.get("p-1") == waiting


def test_형식이_틀린_재진단_요청은_422로_거절한다(client, manager):
    waiting = _waiting(manager)

    response = client.post(RESUME, json=_resume_payload(waiting, answers=[]))

    assert response.status_code == 422
    assert response.json()["code"] == "AI_INVALID_REQUEST"
    assert manager.get("p-1") == waiting


def test_답변_대기_상품을_새_진단으로_다시_보내면_409다(client, manager):
    # 답변 대기는 진행 중 상태. 이어서 진단하려면 resume으로 보내야 함 (#365)
    _waiting(manager)

    response = client.post(CONTENT, json=_payload("p-1"))

    assert response.status_code == 409
    assert response.json()["data"] == {"conflictProductIds": ["p-1"]}
