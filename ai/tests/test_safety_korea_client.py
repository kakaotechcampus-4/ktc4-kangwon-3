"""SafetyKorea 검색 요청의 검색 구분 검증을 실제 호출 없이 검증한다."""

import pytest
from pydantic import ValidationError

from app.schemas.clients.safety_korea_request import (
    CertSearchRequest,
    ForeignRecallSearchRequest,
    RecallSearchRequest,
)


@pytest.mark.parametrize(
    "request_model",
    [CertSearchRequest, RecallSearchRequest, ForeignRecallSearchRequest],
)
def test_정의되지_않은_검색_구분은_요청_전에_거부한다(request_model):
    # 틀린 검색 구분은 API가 필터 없이 전체 목록(748MB)을 돌려준다 (#185).
    with pytest.raises(ValidationError):
        request_model(condition_key="wrongKey", condition_value="XU101030-17003A")


@pytest.mark.parametrize(
    ("request_model", "other_api_key"),
    [
        (CertSearchRequest, "barcodeNum"),          # 국내리콜 전용
        (RecallSearchRequest, "fRecallUid"),        # 국외리콜 전용
        (ForeignRecallSearchRequest, "certNum"),    # KC인증·국내리콜 전용
    ],
)
def test_다른_API의_검색_구분은_거부한다(request_model, other_api_key):
    with pytest.raises(ValidationError):
        request_model(condition_key=other_api_key, condition_value="검색어")


@pytest.mark.parametrize(
    ("request_model", "condition_key"),
    [
        (CertSearchRequest, "certNum"),
        (RecallSearchRequest, "barcodeNum"),
        (ForeignRecallSearchRequest, "fRecallUid"),
    ],
)
def test_API별_허용된_검색_구분은_통과한다(request_model, condition_key):
    request = request_model(condition_key=condition_key, condition_value="검색어")

    assert request.condition_key == condition_key
