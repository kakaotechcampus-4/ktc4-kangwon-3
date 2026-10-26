"""진단 접수·재진단 요청·응답 스키마의 camelCase 경계와 입력 검증을 확인한다."""

import pytest
from pydantic import ValidationError

from app.schemas.request import DiagnosisRequest, ResumeRequest
from app.schemas.response import (
    AcceptedProduct,
    DiagnosisAccepted,
    DiagnosisAcceptedResponse,
    ResumeAccepted,
    ResumeAcceptedResponse,
)


def _product(product_id: str = "p-1", **fields) -> dict:
    return {"productId": product_id, "textBlocks": ["상품 설명"], **fields}


def test_camelCase_요청을_snake_case_필드로_읽는다():
    request = DiagnosisRequest.model_validate({
        "diagnosisId": "d-1",
        "products": [_product(imageUrls=["data:image/png;base64,AAA"], sourceUrl="https://example.com/1")],
    })

    product = request.products[0]
    assert request.diagnosis_id == "d-1"
    assert (product.product_id, product.text_blocks, product.image_urls, product.source_url) == (
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
    empty = {"productId": "p-2", "textBlocks": [], "imageUrls": []}

    with pytest.raises(ValidationError, match="textBlocks 또는 imageUrls"):
        DiagnosisRequest.model_validate({"diagnosisId": "d-1", "products": [_product(), empty]})


@pytest.mark.parametrize("payload", [
    {"diagnosisId": "", "products": [_product()]},
    {"diagnosisId": "d-1", "products": [_product("")]},
    {"diagnosisId": "d-1", "products": [_product()], "extra": 1},
    # 예전 이름은 받지 않음 (#389·#391에서 imageUrls로 변경, BE #392와 함께)
    {"diagnosisId": "d-1", "products": [_product(imagesBase64=["https://example.com/a.jpg"])]},
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
    accepted = DiagnosisAccepted(diagnosis_id="d-1", products=[AcceptedProduct(product_id="p-1", run_id="run-1")])

    assert (accepted.diagnosis_id, accepted.products[0].status) == ("d-1", "accepted")


def test_접수_응답은_data를_camelCase로_내보낸다():
    response = DiagnosisAcceptedResponse(
        code="OK", message="진단 요청이 접수되었습니다.",
        data=DiagnosisAccepted(diagnosis_id="d-1", products=[
            AcceptedProduct(product_id="p-1", run_id="run-1"), AcceptedProduct(product_id="p-2", run_id="run-2"),
        ]),
    )

    assert response.model_dump(by_alias=True) == {
        "code": "OK",
        "message": "진단 요청이 접수되었습니다.",
        "details": None,
        "data": {"diagnosisId": "d-1", "products": [
            {"productId": "p-1", "runId": "run-1", "status": "accepted"},
            {"productId": "p-2", "runId": "run-2", "status": "accepted"},
        ]},
    }


@pytest.mark.parametrize("fields", [
    {"products": []},
    {"products": [{"product_id": "p-1", "run_id": ""}]},
])
def test_접수_응답은_상품과_실행_ID가_비면_만들지_않는다(fields):
    with pytest.raises(ValidationError):
        DiagnosisAccepted(diagnosis_id="d-1", **fields)


def _resume(**fields) -> dict:
    return {
        "diagnosisId": "d-1", "productId": "p-1", "runId": "run-1", "questionRound": 1,
        "answers": [{"questionKey": "battery_only", "answerText": "네"}],
        **fields,
    }


def test_재진단_요청을_camelCase로_읽는다():
    request = ResumeRequest.model_validate(_resume())

    assert (request.diagnosis_id, request.product_id, request.run_id, request.question_round) == (
        "d-1", "p-1", "run-1", 1,
    )
    assert (request.answers[0].question_key, request.answers[0].answer_text) == ("battery_only", "네")


@pytest.mark.parametrize("question_round", [0, 3, "1", True])
def test_재진단_질문_회차는_1이나_2_정수만_받는다(question_round):
    with pytest.raises(ValidationError):
        ResumeRequest.model_validate(_resume(questionRound=question_round))


def test_재진단_답변은_500자까지_받는다():
    request = ResumeRequest.model_validate(_resume(answers=[{"questionKey": "battery_only", "answerText": "가" * 500}]))

    assert len(request.answers[0].answer_text) == 500


def test_재진단_답변의_질문_키_중복을_거부한다():
    answers = [{"questionKey": "battery_only", "answerText": "네"}, {"questionKey": "battery_only", "answerText": "아니요"}]

    with pytest.raises(ValidationError, match="battery_only"):
        ResumeRequest.model_validate(_resume(answers=answers))


@pytest.mark.parametrize("fields", [
    {"answers": []},
    {"runId": ""},
    {"answers": [{"questionKey": "", "answerText": "네"}]},
    {"answers": [{"questionKey": "k" * 51, "answerText": "네"}]},
    {"answers": [{"questionKey": "battery_only", "answerText": ""}]},
    {"answers": [{"questionKey": "battery_only", "answerText": " \n\t"}]},
    {"answers": [{"questionKey": "battery_only", "answerText": "가" * 501}]},
    {"extra": 1},
])
def test_재진단_요청은_빈_값과_정의하지_않은_필드를_거부한다(fields):
    with pytest.raises(ValidationError):
        ResumeRequest.model_validate(_resume(**fields))


def test_재진단_요청은_snake_case_키를_거부한다():
    payload = _resume()
    payload["question_round"] = payload.pop("questionRound")

    with pytest.raises(ValidationError):
        ResumeRequest.model_validate(payload)


def test_재진단_접수_응답은_data를_camelCase로_내보낸다():
    response = ResumeAcceptedResponse(
        code="OK", message="재진단 요청이 접수되었습니다.", data=ResumeAccepted(product_id="p-1", run_id="run-2"),
    )

    assert response.model_dump(by_alias=True)["data"] == {"productId": "p-1", "runId": "run-2", "status": "accepted"}
