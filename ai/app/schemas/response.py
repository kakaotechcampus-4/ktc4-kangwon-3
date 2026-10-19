"""API 공통 응답 스키마. BE의 ApiResponse<T> 형식에 맞춘다."""

from typing import Any, Literal

from pydantic import Field

from .base import ApiModel, StrictModel
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


class AcceptedProduct(ApiModel):
    """접수된 상품 하나 (#310).

    Attributes:
        product_id: 상품 ID (세션 ID).
        run_id: 이번 실행 ID. 이 실행의 콜백에 같은 값이 실림 (BE Product.assignRun으로 저장).
        status: 접수 상태. 항상 accepted.
    """

    product_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"


class DiagnosisAccepted(ApiModel):
    """진단 접수 결과. 이후 결과는 상품별 콜백으로 전달.

    Attributes:
        diagnosis_id: BE 진단서 ID.
        products: 접수된 상품과 상품별 실행 ID.
    """

    diagnosis_id: str = Field(min_length=1)
    products: list[AcceptedProduct] = Field(min_length=1)


class DiagnosisAcceptedResponse(ApiResponse):
    """진단 접수 응답 (202). data에 DiagnosisAccepted가 담긴다."""

    data: DiagnosisAccepted | None = None


class DiagnosisConflict(ApiModel):
    """이미 진행 중인 상품이 섞여 접수를 거절한 경우의 상세 (409).

    Attributes:
        conflict_product_ids: 진행 중인 상품 ID 목록.
    """

    conflict_product_ids: list[str]


class ResumeAccepted(ApiModel):
    """재진단 접수 결과 (#310). 이후 결과는 새 실행 ID로 콜백 전달.

    Attributes:
        product_id: 상품 ID (세션 ID).
        run_id: 새로 발급한 실행 ID (BE Product.assignRun으로 저장).
        status: 접수 상태. 항상 accepted.
    """

    product_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["accepted"] = "accepted"


class ResumeAcceptedResponse(ApiResponse):
    """재진단 접수 응답 (202). data에 ResumeAccepted가 담긴다."""

    data: ResumeAccepted | None = None


def ok(data: Any = None, message: str = "요청이 성공적으로 처리되었습니다.") -> ApiResponse:
    """성공 응답을 생성한다."""
    return ApiResponse(code="OK", message=message, data=data)


def ok_diagnose(data: FinalAssessment, message: str = "진단이 성공적으로 처리되었습니다.") -> DiagnoseResponse:
    """진단 성공 응답을 생성한다."""
    return DiagnoseResponse(code="OK", message=message, data=data)


def fail(code: str, message: str, details: list[FieldErrorDetail] | None = None) -> ApiResponse:
    """실패 응답을 생성한다."""
    return ApiResponse(code=code, message=message, details=details)
