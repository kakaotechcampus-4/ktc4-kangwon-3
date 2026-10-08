"""AI 서버 공통 응답 코드와 예외 (#171 §6).

API 경계에서 ApiResponse{code, message, details, data}로 변환. 내부 원인·stack trace는 비공개.
"""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from .observability.context import PipelineStage


@dataclass(frozen=True)
class ResponseCode:
    """응답 코드 하나의 HTTP 상태·코드·공개 문구.

    Attributes:
        http_status: HTTP 응답 상태. 콜백 전용 코드는 500.
        code: ApiResponse.code, 콜백 errorCode 값.
        message: 공개 문구. 원본 예외 내용은 넣지 않음.
    """

    http_status: int
    code: str
    message: str


class AIResponseCode(Enum):
    """AI 서버 응답 코드 목록. 추가·변경 시 BE 확인."""

    # API 응답
    INVALID_REQUEST = ResponseCode(422, "AI_INVALID_REQUEST", "요청 형식이 올바르지 않습니다.")
    NOT_FOUND = ResponseCode(404, "AI_NOT_FOUND", "요청한 경로를 찾을 수 없습니다.")
    METHOD_NOT_ALLOWED = ResponseCode(405, "AI_METHOD_NOT_ALLOWED", "허용되지 않은 HTTP 메서드입니다.")
    SESSION_CONFLICT = ResponseCode(409, "AI_SESSION_CONFLICT", "이미 진행 중인 상품이 있습니다.")
    QUEUE_FULL = ResponseCode(429, "AI_QUEUE_FULL", "진단 대기열이 가득 찼습니다. 잠시 후 다시 요청해 주세요.")
    INTERNAL_ERROR = ResponseCode(500, "AI_INTERNAL_ERROR", "AI 서버 내부 오류가 발생했습니다.")
    NOT_IMPLEMENTED = ResponseCode(501, "AI_NOT_IMPLEMENTED", "아직 지원하지 않는 기능입니다.")

    # 콜백 errorCode 전용. HTTP 응답으로 쓰지 않음
    PIPELINE_ERROR = ResponseCode(500, "AI_PIPELINE_ERROR", "진단 실행 중 오류가 발생했습니다.")
    TIMEOUT = ResponseCode(500, "AI_TIMEOUT", "진단 시간이 초과되었습니다.")


class AIServiceError(RuntimeError):
    """AI 서버 공통 예외. API 경계에서 응답 코드로 변환됨.

    원인 예외는 ``raise AIServiceError(...) from exc``로 보존.

    Attributes:
        response_code: 응답 코드.
        stage: 실패한 파이프라인 단계. 단계 밖이면 None.
        retryable: 재시도 가능성. 즉시 재시도하라는 의미 아님.
        partial_result: 내부 부분 결과. 응답으로 내보내지 않음.
        data: 응답 data로 공개할 DTO. 문서 §6.1에 없는 확장 필드.
    """

    def __init__(
        self,
        *,
        response_code: ResponseCode,
        stage: PipelineStage | None = None,
        retryable: bool = False,
        partial_result: object | None = None,
        data: BaseModel | None = None,
    ) -> None:
        """예외를 만든다.

        Args:
            response_code: 응답 코드. ``AIResponseCode.X.value``.
            stage: 실패한 파이프라인 단계.
            retryable: 재시도 가능성.
            partial_result: 내부 부분 결과.
            data: 응답 data로 공개할 DTO.
        """
        super().__init__(response_code.message)
        self.response_code = response_code
        self.stage = stage
        self.retryable = retryable
        self.partial_result = partial_result
        self.data = data
