"""진단서 단위 접수 요청·응답 스키마의 camelCase 경계와 입력 검증을 확인한다."""

import pytest
from pydantic import ValidationError

from app.schemas.request import DiagnosisRequest
from app.schemas.response import DiagnosisAccepted, DiagnosisAcceptedResponse


def _product(product_id: str = "p-1", **fields) -> dict:
    return {"productId": product_id, "textBlocks": ["상품 설명"], **fields}


def test_camelCase_요청을_snake_case_필드로_읽는다():
    request = DiagnosisRequest.model_validate({
        "diagnosisId": "d-1",
        "products": [_product(imagesBase64=["data:image/png;base64,AAA"], sourceUrl="https://example.com/1")],
    })

    product = request.products[0]
    assert request.diagnosis_id == "d-1"
    assert (product.product_id, product.text_blocks, product.images_base64, product.source_url) == (
        "p-1", ["상품 설명"], ["data:image/png;base64,AAA"], "https://example.com/1",
    )


@pytest.mark.parametrize("count", [0, 11])
def test_상품은_1개에서_10개까지만_받는다(count):
    products = [_product(f"p-{i}") for i in range(count)]

    with pytest.raises(ValidationError):
        DiagnosisRequest.model_validate({"diagnosisId": "d-1", "products": products})


def test_같은_요청_안의_상품_ID_중복을_거부한다():
    with pytest.raises(ValidationError, match="p-1"):
        DiagnosisRequest.model_validate({"diagnosisId": "d-1", "products": [_product("p-1"), _product("p-1")]})


def test_상품마다_텍스트나_이미지가_하나는_있어야_한다():
    empty = {"productId": "p-2", "textBlocks": [], "imagesBase64": []}

    with pytest.raises(ValidationError, match="textBlocks 또는 imagesBase64"):
        DiagnosisRequest.model_validate({"diagnosisId": "d-1", "products": [_product(), empty]})


@pytest.mark.parametrize("payload", [
    {"diagnosisId": "", "products": [_product()]},
    {"diagnosisId": "d-1", "products": [_product("")]},
    {"diagnosisId": "d-1", "products": [_product()], "extra": 1},
])
def test_빈_ID와_정의하지_않은_필드를_거부한다(payload):
    with pytest.raises(ValidationError):
        DiagnosisRequest.model_validate(payload)


@pytest.mark.parametrize("payload", [
    {"diagnosis_id": "d-1", "products": [_product()]},
    {"diagnosisId": "d-1", "products": [{"product_id": "p-1", "text_blocks": ["상품 설명"]}]},
])
def test_요청은_snake_case_키를_거부한다(payload):
    with pytest.raises(ValidationError):
        DiagnosisRequest.model_validate(payload)


def test_응답은_코드에서_필드_이름으로_만들_수_있다():
    assert DiagnosisAccepted(diagnosis_id="d-1", accepted_product_ids=["p-1"]).diagnosis_id == "d-1"


def test_접수_응답은_data를_camelCase로_내보낸다():
    response = DiagnosisAcceptedResponse(
        code="OK", message="진단 요청이 접수되었습니다.",
        data=DiagnosisAccepted(diagnosis_id="d-1", accepted_product_ids=["p-1", "p-2"]),
    )

    assert response.model_dump(by_alias=True) == {
        "code": "OK",
        "message": "진단 요청이 접수되었습니다.",
        "details": None,
        "data": {"diagnosisId": "d-1", "acceptedProductIds": ["p-1", "p-2"]},
    }
