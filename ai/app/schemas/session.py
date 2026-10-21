"""진단 세션 상태 스키마. 상품 1개 = 세션 1개 (#263)."""

from datetime import timezone
from enum import StrEnum

from pydantic import AwareDatetime, Field, field_validator

from ..observability.context import ExecutionContext, PipelineStage
from .agent import ExtractionInput
from .base import StrictModel, utc_now
from .callback import PublicQuestionDto
from .schemas import ExecutionEndReason, FinalAssessment


class SessionStatus(StrEnum):
    """세션 진행 상태.

    AWAITING_INPUT: 사용자 답변 대기. 실행은 끝났고, 세션 기록을 지우지 않고 보관했다가 답변이 오면
        새 실행으로 이어서 진단 (#263, #310). BE와 연결을 유지하는 상태가 아님.
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


class SessionAnswer(StrictModel):
    """사용자 답변 하나. 상품 원문과 섞지 않고 사용자 답변 출처로 따로 보관 (#319).

    Attributes:
        question_round: 답한 질문 회차.
        question_key: 답한 질문 키.
        answer_text: 사용자 답변.
    """

    question_round: int = Field(ge=1, strict=True)
    question_key: str = Field(min_length=1)
    answer_text: str = Field(min_length=1)


class DiagnosisInput(StrictModel):
    """진단 함수가 받는 실행 한 번의 입력. 첫 실행은 원래 입력만, 재진단은 이전 결과·답변까지.

    Attributes:
        source: 접수 때 받은 원래 입력.
        previous: 재진단이면 이전 실행 결과(추출 결과 포함). 첫 실행이면 None.
        answers: 지금까지 받은 사용자 답변. 첫 실행이면 빈 목록.
    """

    source: ExtractionInput
    previous: FinalAssessment | None = None
    answers: list[SessionAnswer] = Field(default_factory=list)


class DiagnosisSession(StrictModel):
    """진단 세션 한 건의 현재 상태.

    Attributes:
        context: 실행 컨텍스트 (#171 §2). context.product_id가 세션 ID (BE 상품 UUID v7).
        source: 접수 때 받은 원래 입력. 재진단에 다시 씀.
        status: 진행 상태.
        stage: 현재 단계 (#171 PipelineStage). 실행 전이면 None.
        termination_reason: 실행 종료 사유. 종료 전이거나 실패면 None.
        result: 진단 결과. 결과 없이 끝났으면 None. 추출 결과(result.product)도 여기 있음.
        question_round: 마지막으로 보낸 질문 회차. 질문 전이면 0.
        questions: 그 회차에 보낸 질문. 질문 콜백과 재진단 답변 검사의 기준.
        answers: 지금까지 받은 사용자 답변. 회차 순으로 누적.
        error_code: 실패 코드. 실패가 아니면 None.
        retryable: 같은 요청을 다시 보내 복구 가능한지. 실패가 아니면 None.
        accepted_at: 접수 시각 (UTC).
        started_at: 실행 시작 시각 (UTC). 대기 시간·실행 시간을 나눠 재는 데 씀. 실행 전이면 None.
        stage_started_at: 현재 단계 시작 시각 (UTC). 실행 전이면 None.
        updated_at: 마지막 상태 변경 시각 (UTC).
    """

    context: ExecutionContext
    source: ExtractionInput
    status: SessionStatus = SessionStatus.ACCEPTED
    stage: PipelineStage | None = None
    termination_reason: ExecutionEndReason | None = None
    result: FinalAssessment | None = None
    question_round: int = Field(default=0, ge=0, strict=True)
    questions: list[PublicQuestionDto] = Field(default_factory=list)
    answers: list[SessionAnswer] = Field(default_factory=list)
    error_code: str | None = None
    retryable: bool | None = None
    accepted_at: AwareDatetime = Field(default_factory=utc_now)
    started_at: AwareDatetime | None = None
    stage_started_at: AwareDatetime | None = None
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    # #171 §7.1 timestamp 규칙: 시간대가 있는 입력은 UTC로 정규화
    @field_validator("accepted_at", "started_at", "stage_started_at", "updated_at")
    @classmethod
    def _to_utc(cls, value: AwareDatetime | None) -> AwareDatetime | None:
        return value.astimezone(timezone.utc) if value is not None else None
