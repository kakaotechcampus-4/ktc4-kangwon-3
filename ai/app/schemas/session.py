"""진단 세션 상태 스키마. 상품 1개 = 세션 1개 (#263)."""

from datetime import timezone
from enum import StrEnum

from pydantic import AwareDatetime, Field, field_validator

from ..observability.context import ExecutionContext, PipelineStage
from .base import StrictModel, utc_now
from .callback import PublicQuestionDto
from .schemas import ExecutionEndReason, FinalAssessment


class SessionStatus(StrEnum):
    """세션 진행 상태.

    AWAITING_INPUT: 사용자 답변 대기. 세션을 끊지 않고 답변 후 이어서 진단 (#263).
    COMPLETED: 실행 종료. termination_reason은 #171 §7.1.1 종료 사유 중 하나.
        검증 완료를 뜻하지 않음. REVISION_REQUIRED·RETRY_LIMIT_EXCEEDED 등으로 끝나 result.verification_status가
        INCOMPLETE여도 COMPLETED. 검증 결과는 result.verification_status와 termination_reason으로 확인.
    FAILED: 미처리 예외. 종료 사유로 바꾸지 않고 error_code로 기록 (#171 §7.1.1).
    """

    ACCEPTED = "accepted"
    RUNNING = "running"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosisSession(StrictModel):
    """진단 세션 한 건의 현재 상태.

    Attributes:
        context: 실행 컨텍스트 (#171 §2). context.product_id가 세션 ID (BE 상품 UUID v7).
        status: 진행 상태.
        stage: 현재 단계 (#171 PipelineStage). 실행 전이면 None.
        termination_reason: 실행 종료 사유. 종료 전이거나 실패면 None.
        result: 진단 결과. 결과 없이 끝났으면 None.
        question_round: 마지막으로 보낸 질문 회차. 질문 전이면 0.
        questions: 그 회차에 보낸 질문. 질문 콜백과 재진단 답변 검사의 기준.
        error_code: 실패 코드. 실패가 아니면 None.
        retryable: 같은 요청을 다시 보내 복구 가능한지. 실패가 아니면 None.
        accepted_at: 접수 시각 (UTC).
        stage_started_at: 현재 단계 시작 시각 (UTC). 실행 전이면 None.
        updated_at: 마지막 상태 변경 시각 (UTC).
    """

    context: ExecutionContext
    status: SessionStatus = SessionStatus.ACCEPTED
    stage: PipelineStage | None = None
    termination_reason: ExecutionEndReason | None = None
    result: FinalAssessment | None = None
    question_round: int = Field(default=0, ge=0, strict=True)
    questions: list[PublicQuestionDto] = Field(default_factory=list)
    error_code: str | None = None
    retryable: bool | None = None
    accepted_at: AwareDatetime = Field(default_factory=utc_now)
    stage_started_at: AwareDatetime | None = None
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    # #171 §7.1 timestamp 규칙: 시간대가 있는 입력은 UTC로 정규화
    @field_validator("accepted_at", "stage_started_at", "updated_at")
    @classmethod
    def _to_utc(cls, value: AwareDatetime | None) -> AwareDatetime | None:
        return value.astimezone(timezone.utc) if value is not None else None
