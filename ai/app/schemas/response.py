"""API 공통 응답 스키마. BE의 ApiResponse<T> 형식에 맞춘다."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from ..domain.context import PipelineStage
from .base import ApiModel, StrictModel
from .callback import PublicAssessmentDto, PublicQuestionDto
from .schemas import FinalAssessment
from .session import SessionStatus


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
    """이미 실행 중인 상품이 섞여 접수를 거절한 경우의 상세 (409).

    Attributes:
        conflict_product_ids: 실행 중인 상품 ID 목록.
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


class UnknownQuestionKeys(ApiModel):
    """이번 회차에 묻지 않은 질문의 답변이 섞여 재진단을 거절한 경우의 상세 (400).

    Attributes:
        question_keys: 묻지 않은 질문 키 목록.
    """

    question_keys: list[str]


def ok(data: Any = None, message: str = "요청이 성공적으로 처리되었습니다.") -> ApiResponse:
    """성공 응답을 생성한다."""
    return ApiResponse(code="OK", message=message, data=data)


def fail(code: str, message: str, details: list[FieldErrorDetail] | None = None) -> ApiResponse:
    """실패 응답을 생성한다."""
    return ApiResponse(code=code, message=message, details=details)


class DevDiagnosisAccepted(ApiModel):
    """샌드박스 진단 접수 결과. 요청 순서대로 발급한 상품 ID·실행 ID.

    Attributes:
        products: 접수된 상품별 상품 ID·실행 ID.
    """

    products: list[AcceptedProduct] = Field(min_length=1)


class DevDiagnosisAcceptedResponse(ApiResponse):
    """샌드박스 진단 접수 응답 (202). data에 DevDiagnosisAccepted."""

    data: DevDiagnosisAccepted | None = None


class DevDiagnosisStatus(ApiModel):
    """개발용 진단 상태 (#318). BE가 콜백으로 받을 공개 진단서·질문과 내부 결과를 함께 담음.

    Attributes:
        product_id: 개발용 상품 ID (dev-).
        run_id: 실행 ID.
        status: 세션 상태.
        stage: 현재(또는 마지막) 단계.
        error_code: 실패 코드. 실패가 아니면 None.
        retryable: 실패 시 다시 요청해도 되는지.
        accepted_at: 접수 시각.
        updated_at: 마지막 변경 시각.
        assessment: 완료 시 BE에 결과 콜백으로 갈 공개 진단서.
        question_round: 답변 대기 시 질문 회차.
        questions: 답변 대기 시 BE에 질문 콜백으로 갈 질문.
        presentation_error: 공개 진단서·질문 변환 실패 내용. 운영이라면 실패 콜백으로 끝나는 경우.
        result: 내부 진단 결과 (Tool별 결과·검증 포함). 디버깅용.
    """

    product_id: str
    run_id: str
    status: SessionStatus
    stage: PipelineStage | None = None
    error_code: str | None = None
    retryable: bool | None = None
    accepted_at: datetime
    updated_at: datetime
    assessment: PublicAssessmentDto | None = None
    question_round: int | None = None
    questions: list[PublicQuestionDto] = Field(default_factory=list)
    presentation_error: str | None = None
    result: FinalAssessment | None = None


class DevDiagnosisStatusResponse(ApiResponse):
    """개발용 진단 상태 조회 응답. data에 DevDiagnosisStatus."""

    data: DevDiagnosisStatus | None = None
