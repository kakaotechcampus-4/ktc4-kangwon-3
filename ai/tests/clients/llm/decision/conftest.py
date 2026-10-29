"""판단 클라이언트 테스트 공통 요청. 질문 세 종류를 하나씩 담음."""

import pytest

from app.schemas.clients.decision_request import DecisionRequest

BASE_URL = "https://gateway.test/v1"
API_KEY = "test-api-key"


@pytest.fixture
def decision_request() -> DecisionRequest:
    """예/아니오·고르기·점수 질문을 하나씩 담은 판단 요청. 설명 없는 후보·단계 포함."""
    return DecisionRequest(
        model="test/decision-model",
        subject={"product_name": "색연필 24색 세트", "for_children": False},
        questions=[
            {"type": "yes_no", "name": "kind_kids", "instructions": "어린이가 주로 쓰는 종류인가"},
            {
                "type": "choice", "name": "category", "instructions": "상품 종류",
                "options": [{"value": "stationery", "description": "학용품·문구"}, {"value": "other"}],
            },
            {
                "type": "score", "name": "kid_use", "instructions": "어린이가 쓰는 정도",
                "levels": [{"value": "low", "description": "거의 없음"}, {"value": "mid"}, {"value": "high"}],
            },
        ],
    )
