"""API 공통 응답 스키마. BE의 ApiResponse<T> 형식에 맞춘다."""

from typing import Any

from pydantic import Field

from .base import StrictModel
from .schemas import FinalAssessment


class FieldErrorDetail(StrictModel):
    """요청 필드 검증 실패 상세."""

    field: str
    message: str


class ApiResponse(StrictModel):
    """BE ApiResponse<T>와 동일한 공통 응답 껍데기.

    Returns:
        code: 응답 코드 (예: "OK", "COMMON-001").
        message: 사람이 읽을 수 있는 메시지.
        details: 필드 검증 오류 목록 (없으면 null).
        data: 응답 본문 (없으면 null).
    """

    code: str
    message: str
    details: list[FieldErrorDetail] | None = None
    data: Any = None


class DiagnoseResponse(ApiResponse):
    """진단 파이프라인 응답. data에 FinalAssessment가 담긴다."""

    data: FinalAssessment | None = None


def ok(data: Any = None, message: str = "요청이 성공적으로 처리되었습니다.") -> ApiResponse:
    """성공 응답을 생성한다."""
    return ApiResponse(code="OK", message=message, data=data)


def ok_diagnose(data: FinalAssessment, message: str = "진단이 성공적으로 처리되었습니다.") -> DiagnoseResponse:
    """진단 성공 응답을 생성한다."""
    return DiagnoseResponse(code="OK", message=message, data=data)


def fail(code: str, message: str, details: list[FieldErrorDetail] | None = None) -> ApiResponse:
    """실패 응답을 생성한다."""
    return ApiResponse(code=code, message=message, details=details)
