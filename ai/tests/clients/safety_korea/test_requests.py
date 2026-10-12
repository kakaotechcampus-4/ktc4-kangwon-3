"""SafetyKorea 검색 요청의 검색 구분 허용값을 검증한다.

정의되지 않은 검색 구분을 넣으면 API가 에러 대신 필터 없는 전체 목록(KC인증 약 105만 건)을 돌려줌 (#185).
"""

import pytest
from pydantic import ValidationError

from app.schemas.clients.safety_korea_request import (
    CertSearchRequest,
    ForeignRecallSearchRequest,
    RecallSearchRequest,
)


@pytest.mark.parametrize("request_model", [CertSearchRequest, RecallSearchRequest, ForeignRecallSearchRequest])
def test_정의되지_않은_검색_구분은_요청_전에_거부한다(request_model):
    with pytest.raises(ValidationError):
        request_model(condition_key="unknownKey", condition_value="x")


@pytest.mark.parametrize(
    ("request_model", "other_api_key"),
    [(CertSearchRequest, "recallProductName"), (RecallSearchRequest, "fRecallUid"), (ForeignRecallSearchRequest, "certNum")],
)
def test_다른_API의_검색_구분은_거부한다(request_model, other_api_key):
    with pytest.raises(ValidationError):
        request_model(condition_key=other_api_key, condition_value="x")


@pytest.mark.parametrize(
    ("request_model", "condition_key"),
    [(CertSearchRequest, "certNum"), (RecallSearchRequest, "publishDate"), (ForeignRecallSearchRequest, "recallModelName")],
)
def test_API별_허용된_검색_구분은_통과한다(request_model, condition_key):
    assert request_model(condition_key=condition_key, condition_value="x").condition_key == condition_key
