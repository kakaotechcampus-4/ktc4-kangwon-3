"""더미 진단 라우터: 케이스 표시를 붙여 더미로 접수하고, 다른 경로 세션의 재진단은 404로 거절하는지 확인한다."""

from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.domain.context import ExecutionContext, RunType
from app.dummy import DummyCaseName, read_case
from app.main import app
from app.routers._dummy import DummyAssessmentPresenter, build_dummy_assessment
from app.routers.diagnose import get_session_manager
from app.schemas.agent import ExtractionInput
from app.schemas.base import utc_now
from app.schemas.callback import PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, OverallStatus
from app.schemas.session import DiagnosisSession
from app.sessions.job import JobDone
from app.sessions.manager import SessionManager
from app.sessions.store import SessionStore
from app.sessions.transitions import AskUser, Start, apply

CONTENT = "/api/ai/v1/dummy/diagnose/content"
RESUME = "/api/ai/v1/dummy/diagnose/resume"
PRODUCTION_RESUME = "/api/ai/v1/diagnose/resume"
_QUESTIONS = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]


def _payload(*product_ids: str) -> dict:
    return {"diagnosisId": "d-1", "products": [{"productId": pid, "textBlocks": ["상품 설명"]} for pid in product_ids]}


@pytest.fixture
def manager():
    """lifespan 대신 쓰는 세션 관리자. 관문이 열릴 때까지 진단이 끝나지 않음."""
    gate = Event()

    def job(job_input, context, progress):
        gate.wait(timeout=5)
        return JobDone(build_dummy_assessment(job_input.source.product_id))

    store = SessionStore()
    instance = SessionManager(store, job)
    instance.store = store
    yield instance
    gate.set()
    instance.shutdown(wait=True)


@pytest.fixture
def client(manager) -> TestClient:
    app.dependency_overrides[get_session_manager] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def _waiting(manager: SessionManager, run_type: RunType) -> DiagnosisSession:
    """질문으로 끝나 답변을 기다리는 세션. 전이표로 만들어 저장소에 직접 넣음."""
    now = utc_now()
    context = ExecutionContext.start(product_id="p-1", run_type=run_type, diagnosis_id="d-1")
    source = ExtractionInput(product_id="p-1")
    session = apply(DiagnosisSession(context=context, source=source), Start(), now=now).session
    awaiting = build_dummy_assessment("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })
    waiting = apply(session, AskUser(awaiting, _QUESTIONS), now=now).session
    manager.store.add([waiting])
    return waiting


def _resume_payload(waiting: DiagnosisSession) -> dict:
    return {
        "diagnosisId": "d-1", "productId": "p-1", "runId": waiting.context.run_id,
        "questionRound": waiting.question_round, "answers": [{"questionKey": "battery_only", "answerText": "네"}],
    }


def test_지정한_케이스를_입력에_남겨_더미로_접수한다(client, manager):
    response = client.post(f"{CONTENT}?case=tumbler", json=_payload("p-1", "p-2"))

    assert response.status_code == 202
    assert [product["productId"] for product in response.json()["data"]["products"]] == ["p-1", "p-2"]
    for product_id in ("p-1", "p-2"):
        session = manager.get(product_id)
        assert session.context.run_type is RunType.DUMMY
        assert read_case(session.source) is DummyCaseName.TUMBLER
        assert session.source.text_blocks[0] == "상품 설명"


def test_케이스를_빼면_상품마다_골라_남긴다(client, manager):
    response = client.post(CONTENT, json=_payload("p-1", "p-2"))

    assert response.status_code == 202
    assert all(read_case(manager.get(product_id).source) in DummyCaseName for product_id in ("p-1", "p-2"))


def test_없는_케이스_값은_422로_거절하고_접수하지_않는다(client, manager):
    response = client.post(f"{CONTENT}?case=unknown", json=_payload("p-1"))

    assert response.status_code == 422
    assert manager.get("p-1") is None


def test_더미_세션은_더미_경로로_재진단한다(client, manager):
    waiting = _waiting(manager, RunType.DUMMY)

    response = client.post(RESUME, json=_resume_payload(waiting))

    assert response.status_code == 202
    assert manager.get("p-1").context.run_type is RunType.DUMMY


@pytest.mark.parametrize(("run_type", "route"), [(RunType.PRODUCTION, RESUME), (RunType.DUMMY, PRODUCTION_RESUME)])
def test_다른_경로로_접수한_세션의_재진단은_404로_거절한다(client, manager, run_type, route):
    waiting = _waiting(manager, run_type)

    response = client.post(route, json=_resume_payload(waiting))

    assert response.status_code == 404
    assert manager.get("p-1") == waiting


def test_임시_변환기는_가짜_진단_결과를_분야_카드와_법령_근거가_있는_공개_진단서로_바꾼다():
    assessment = DummyAssessmentPresenter().assessment(build_dummy_assessment("p-1"))

    cards = {review.tool_name: review for review in assessment.tool_reviews}
    assert set(cards) == {"CUSTOMS", "RADIO", "FOOD_DRUG", "ELECTRICAL", "CHILDREN", "LABEL_AD"}
    # 건너뛴 Tool은 SKIPPED 카드, 판단마다 법령 근거 하나 이상
    assert (cards["FOOD_DRUG"].status, cards["FOOD_DRUG"].findings) == ("SKIPPED", [])
    assert all(finding.legal_sources for review in assessment.tool_reviews for finding in review.findings)
    assert assessment.required_actions and assessment.notices


@pytest.mark.parametrize(("update", "expected"), [
    ({}, ("completed", "DIRECT_IMPORT_CERTIFICATION_REQUIRED")),
    ({"overall_status": OverallStatus.LIKELY_COMPLIANT}, ("completed", "PURCHASING_AGENT_ALLOWED")),
    (
        {
            "verification_status": FinalVerificationStatus.INCOMPLETE,
            "termination_reason": ExecutionEndReason.QUESTION_LIMIT_EXCEEDED,
        },
        ("incomplete", "RECHECK_REQUIRED"),
    ),
])
def test_임시_변환기는_검증_상태와_종합_판단으로_결과_상태를_정한다(update, expected):
    result = build_dummy_assessment("p-1").model_copy(update=update)

    assessment = DummyAssessmentPresenter().assessment(result)

    assert (assessment.status, assessment.result_status) == expected
