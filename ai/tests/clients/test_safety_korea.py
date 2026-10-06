"""SafetyKorea 검색 요청 검증과 결과 대조를 실제 호출 없이 검증한다."""

import pytest
from pydantic import ValidationError

from app.clients.safety_korea import SafetyKoreaClient
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


def _client_returning(result_data: list[dict]) -> SafetyKoreaClient:
    client = SafetyKoreaClient(auth_key="unused")
    client._fetch = lambda endpoint, params: {"resultCode": "2000", "resultData": result_data}
    return client


def test_인증번호_조회는_요청_번호와_일치하는_항목만_반환한다():
    # 필터가 무시되면 요청과 무관한 인증(YU102511-26007)이 첫 항목으로 온다 (#185).
    client = _client_returning([
        {"certNum": "YU102511-26007", "productName": "전기용품", "certState": "적합"},
        {"certNum": "XU101030-17003A", "productName": "전지", "certState": "적합"},
    ])

    result = client.search_certifications(
        CertSearchRequest(condition_key="certNum", condition_value="XU101030-17003A")
    )

    assert [item.cert_num for item in result.items] == ["XU101030-17003A"]


def test_인증번호_조회에_일치하는_항목이_없으면_빈_목록을_반환한다():
    client = _client_returning([{"certNum": "YU102511-26007", "productName": "전기용품"}])

    result = client.search_certifications(
        CertSearchRequest(condition_key="certNum", condition_value="XU101030-17003A")
    )

    assert result.items == []


def test_인증번호_외_검색은_결과를_거르지_않는다():
    # 상품명 검색은 여러 인증이 오는 것이 정상이다.
    client = _client_returning([
        {"certNum": "YU102511-26007", "productName": "전지"},
        {"certNum": "XU101030-17003A", "productName": "전지"},
    ])

    result = client.search_certifications(CertSearchRequest(condition_key="productName", condition_value="전지"))

    assert len(result.items) == 2
