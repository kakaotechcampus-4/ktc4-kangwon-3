"""API 오류를 ApiResponse 공통 형식으로 바꾸는 예외 핸들러 (#171 §6.3).

응답에는 응답 코드·공개 문구·필드 오류·공개 DTO만 포함. 원본 예외·입력값·stack trace는 비공개.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import AIResponseCode, AIServiceError, ResponseCode
from .schemas.response import ApiResponse, FieldErrorDetail

logger = logging.getLogger(__name__)

# 프레임워크가 직접 내는 HTTP 오류. 앱 코드는 HTTPException 대신 AIServiceError 사용
_HTTP_STATUS_CODES = {
    404: AIResponseCode.NOT_FOUND.value,
    405: AIResponseCode.METHOD_NOT_ALLOWED.value,
}
# 요청 위치 접두어. 필드 경로에서 제외
_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})
_VALUE_ERROR_PREFIX = "Value error, "


def _respond(
    status_code: int,
    response_code: ResponseCode,
    *,
    details: list[FieldErrorDetail] | None = None,
    data: BaseModel | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """응답 코드를 ApiResponse JSON 응답으로 만든다."""
    body = ApiResponse(code=response_code.code, message=response_code.message, details=details, data=data)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", by_alias=True),
        headers=headers,
    )


def _field_path(loc: tuple[str | int, ...]) -> str:
    """검증 오류 위치를 ``products[0].productId`` 형태로 바꾼다."""
    parts = list(loc[1:] if loc and loc[0] in _LOCATION_PREFIXES else loc)
    if not parts:
        # 요청 본문 전체에 걸린 검증 (상품 ID 중복 등)
        return str(loc[0]) if loc else ""
    path = str(parts[0])
    for part in parts[1:]:
        # 목록 위치는 [0], 필드는 .이름
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _field_errors(exc: RequestValidationError) -> list[FieldErrorDetail]:
    """검증 오류를 필드별 상세로 바꾼다. 입력값(input)은 넣지 않음."""
    return [
        FieldErrorDetail(field=_field_path(tuple(error["loc"])), message=error["msg"].removeprefix(_VALUE_ERROR_PREFIX))
        for error in exc.errors()
    ]


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    response_code = AIResponseCode.INVALID_REQUEST.value
    return _respond(response_code.http_status, response_code, details=_field_errors(exc))


async def _handle_service_error(request: Request, exc: AIServiceError) -> JSONResponse:
    response_code = exc.response_code
    if response_code.http_status >= 500:
        logger.error(
            "AI 서비스 오류 (%s %s, code=%s, stage=%s)",
            request.method, request.url.path, response_code.code, exc.stage, exc_info=exc,
        )
    return _respond(response_code.http_status, response_code, data=exc.data)


async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    response_code = _HTTP_STATUS_CODES.get(exc.status_code, AIResponseCode.INTERNAL_ERROR.value)
    # 405의 Allow 등 프레임워크가 붙인 헤더 유지
    return _respond(exc.status_code, response_code, headers=exc.headers)


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # stack trace는 서버가 다시 던진 예외로 uvicorn이 기록. 여기서는 요청만 남김
    logger.error("처리되지 않은 예외 (%s %s): %s", request.method, request.url.path, type(exc).__name__)
    response_code = AIResponseCode.INTERNAL_ERROR.value
    return _respond(response_code.http_status, response_code)


def register_exception_handlers(app: FastAPI) -> None:
    """앱에 공통 예외 핸들러를 등록한다.

    Args:
        app: 핸들러를 등록할 FastAPI 앱.
    """
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(AIServiceError, _handle_service_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
