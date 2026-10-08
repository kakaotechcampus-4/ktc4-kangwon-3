"""예외 핸들러가 모든 오류를 ApiResponse 형식으로 바꾸고 내부 정보를 숨기는지 확인한다."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AIResponseCode, AIServiceError
from app.exception_handlers import register_exception_handlers
from app.main import app as main_app
from app.observability.context import PipelineStage
from app.schemas.request import DiagnosisRequest
from app.schemas.response import DiagnosisConflict


def _build_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.post("/validate")
    async def validate(req: DiagnosisRequest) -> dict:
        return {}

    @test_app.get("/conflict")
    async def conflict() -> dict:
        raise AIServiceError(
            response_code=AIResponseCode.SESSION_CONFLICT.value,
            data=DiagnosisConflict(conflict_product_ids=["p-1"]),
        )

    @test_app.get("/service-failure")
    async def service_failure() -> dict:
        try:
            raise ConnectionError("내부 주소 10.0.0.1 연결 실패")
        except ConnectionError as exc:
            raise AIServiceError(
                response_code=AIResponseCode.PIPELINE_ERROR.value,
                stage=PipelineStage.EXTRACTION,
                retryable=True,
                partial_result={"secret": "부분 결과"},
            ) from exc

    @test_app.get("/crash")
    async def crash() -> dict:
        raise KeyError("내부 키 secret_token")

    @test_app.get("/framework/{status_code}")
    async def framework_error(status_code: int) -> dict:
        # 프레임워크·미들웨어가 내는 HTTP 오류 흉내
        raise StarletteHTTPException(status_code=status_code)

    @test_app.get("/not-implemented")
    async def not_implemented() -> dict:
        raise AIServiceError(response_code=AIResponseCode.NOT_IMPLEMENTED.value)

    return test_app


@pytest.fixture
def client() -> TestClient:
    # 처리되지 않은 예외도 500 응답으로 확인
    return TestClient(_build_app(), raise_server_exceptions=False)


def test_검증_오류는_422와_필드별_상세로_바꾼다(client):
    response = client.post("/validate", json={"diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": [1]}]})

    assert response.status_code == 422
    assert response.json() == {
        "code": "AI_INVALID_REQUEST",
        "message": "요청 형식이 올바르지 않습니다.",
        "details": [{"field": "products[0].textBlocks[0]", "message": "Input should be a valid string"}],
        "data": None,
    }


def test_모델_검증기_오류는_접두어를_떼고_입력값은_넣지_않는다(client):
    payload = {"diagnosisId": "d-1", "products": [{"productId": "p-9", "textBlocks": ["a"]}, {"productId": "p-9", "textBlocks": ["b"]}]}

    body = client.post("/validate", json=payload).json()

    assert body["details"] == [{"field": "body", "message": "productId가 중복됩니다: p-9"}]
    assert "input" not in str(body)


def test_snake_case_키는_camelCase_필드_누락과_정의되지_않은_필드로_알린다(client):
    body = client.post("/validate", json={"diagnosis_id": "d-1", "products": [{"productId": "p-1", "textBlocks": ["a"]}]}).json()

    fields = {detail["field"] for detail in body["details"]}
    assert fields == {"diagnosisId", "diagnosis_id"}


def test_JSON_문법_오류는_문자_위치_대신_body로_알린다(client):
    response = client.post("/validate", content='{"diagnosisId":', headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json()["details"] == [{"field": "body", "message": "JSON decode error"}]


def test_AIServiceError는_코드의_상태와_공개_data로_응답한다(client):
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "code": "AI_SESSION_CONFLICT",
        "message": "이미 진행 중인 상품이 있습니다.",
        "details": None,
        "data": {"conflictProductIds": ["p-1"]},
    }


def test_AIServiceError의_원인_단계_재시도_부분_결과는_응답에_넣지_않는다(client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.exception_handlers"):
        response = client.get("/service-failure")

    assert response.status_code == 500
    assert response.json() == {
        "code": "AI_PIPELINE_ERROR",
        "message": "진단 실행 중 오류가 발생했습니다.",
        "details": None,
        "data": None,
    }
    # 원인은 서버 로그에만 남음
    assert "10.0.0.1" in caplog.text
    assert "extraction" in caplog.text


def test_처리되지_않은_예외는_500과_공개_문구만_반환한다(client):
    response = client.get("/crash")

    assert response.status_code == 500
    assert response.json() == {
        "code": "AI_INTERNAL_ERROR",
        "message": "AI 서버 내부 오류가 발생했습니다.",
        "details": None,
        "data": None,
    }
    assert "secret_token" not in response.text


def test_없는_경로는_404_공통_형식으로_응답한다(client):
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "AI_NOT_FOUND"


def test_허용되지_않은_메서드는_405와_Allow_헤더를_유지한다(client):
    response = client.get("/validate")

    assert response.status_code == 405
    assert response.json()["code"] == "AI_METHOD_NOT_ALLOWED"
    assert response.headers["allow"] == "POST"


def test_UTF8이_아닌_본문은_400과_요청_오류_코드로_응답한다(client):
    # #283 리뷰: 프레임워크가 본문을 읽지 못해 내는 400
    response = client.post("/validate", content=b'{"diagnosisId": "\xff\xfe"}', headers={"Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json()["code"] == "AI_INVALID_REQUEST"


@pytest.mark.parametrize(
    ("status_code", "code"),
    [(400, "AI_INVALID_REQUEST"), (413, "AI_INVALID_REQUEST"), (418, "AI_INVALID_REQUEST"), (503, "AI_INTERNAL_ERROR")],
)
def test_표에_없는_HTTP_오류는_상태_범위로_코드를_정한다(client, status_code, code):
    response = client.get(f"/framework/{status_code}")

    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_미구현_501은_오류_로그를_남기지_않는다(client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.exception_handlers"):
        response = client.get("/not-implemented")

    assert (response.status_code, response.json()["code"]) == (501, "AI_NOT_IMPLEMENTED")
    assert caplog.records == []


def test_실제_앱에도_핸들러가_등록되어_있다():
    response = TestClient(main_app).get("/api/ai/v1/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "AI_NOT_FOUND"


def _response_422_schema(operation: dict) -> str | None:
    schema = operation.get("responses", {}).get("422", {}).get("content", {}).get("application/json", {}).get("schema", {})
    return schema.get("$ref", "").rsplit("/", 1)[-1] or None


def test_Swagger의_422는_요청_본문이_있는_API만_공통_응답_형식으로_표시한다():
    # #283 리뷰: 기본 HTTPValidationError 대신 실제 응답 형식(ApiResponse)
    paths = main_app.openapi()["paths"]
    body_routes = [
        ("/api/ai/v1/diagnose/content", "post"),
        ("/api/ai/v1/diagnose/url", "post"),
        ("/api/ai/v1/dummy/diagnose/content", "post"),
        ("/api/ai/v1/dummy/diagnose/url", "post"),
    ]

    assert [_response_422_schema(paths[path][method]) for path, method in body_routes] == ["ApiResponse"] * 4
    # 본문 없는 health에는 422가 붙지 않음
    assert "422" not in paths["/api/ai/v1/health"]["get"]["responses"]
    assert "422" not in paths["/api/ai/v1/health/ready"]["get"]["responses"]
