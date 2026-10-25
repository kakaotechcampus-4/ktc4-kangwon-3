"""BE 연동 테스트용 더미 진단 라우터 테스트."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers._dummy import DummyAssessmentPresenter, build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, OverallStatus

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
