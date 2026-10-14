"""AI → BE 진단 콜백 이벤트와 공개 진단서 스키마 (#301, #310).

콜백 수신 경로: POST /internal/v1/ai/products/{productId} (#263). 이벤트 종류는 eventType 하나로 구분.
질문·결과·실패 이벤트는 그 실행(runId)의 마지막 이벤트.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ApiModel
from .schemas import Determination, RiskLevel, ToolName


class PublicPipelineStage(StrEnum):
    """BE에 공개하는 진행 단계. 내부 전용 단계(pipeline)는 공개하지 않음."""

    EXTRACTION = "extraction"
    SELECTION = "selection"
    TOOL_EXECUTION = "tool_execution"
    AGGREGATION = "aggregation"
    VERIFICATION = "verification"
    FINALIZATION = "finalization"


class ProductEventBase(ApiModel):
    """콜백 공통 필드.

    Attributes:
        event_id: 이벤트 ID. BE가 중복 수신을 거르는 키.
        diagnosis_id: BE 진단서 ID.
        product_id: BE 상품 ID (AI 세션 ID).
        run_id: 실행 ID. 재실행마다 새로 발급.
        sequence: 실행 안에서의 이벤트 순서. 실행마다 1부터.
    """

    event_id: str = Field(min_length=1)
    diagnosis_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1, strict=True)


class ProductProgressEvent(ProductEventBase):
    """진행 콜백. BE는 저장하지 않고 화면 표시에만 씀."""

    event_type: Literal["product_progress"] = "product_progress"
    stage: PublicPipelineStage
    stage_status: Literal["started", "completed", "skipped"]
    tool_name: ToolName | None = None

    @model_validator(mode="after")
    def validate_tool_stage(self):
        if self.tool_name is not None and self.stage is not PublicPipelineStage.TOOL_EXECUTION:
            raise ValueError("tool_name은 Tool 실행 단계에서만 전달합니다.")
        return self


class PublicQuestionDto(ApiModel):
    """사용자에게 물을 질문 하나. BE ProductQuestion 저장 형식."""

    question_key: str = Field(min_length=1, max_length=50)
    question_order: int = Field(ge=1, strict=True)
    question_text: str = Field(min_length=1)
    help_text: str | None = None


class ProductAwaitingInputEvent(ProductEventBase):
    """질문 콜백. 이 실행의 마지막. 질문은 최대 2회차, 2회차에는 새 키만."""

    event_type: Literal["product_awaiting_input"] = "product_awaiting_input"
    question_round: int = Field(ge=1, le=2, strict=True)
    questions: list[PublicQuestionDto] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_keys_and_order(self):
        keys = [question.question_key for question in self.questions]
        orders = [question.question_order for question in self.questions]
        if len(keys) != len(set(keys)) or len(orders) != len(set(orders)):
            raise ValueError("질문 키와 순서는 중복될 수 없습니다.")
        return self


class PublicLegalSourceDto(ApiModel):
    source_name: str = Field(min_length=1)
    law_name: str | None = None
    article: str | None = None
    quoted_text: str | None = None
    source_url: str | None = None
    effective_date: str | None = None


class PublicFindingDto(ApiModel):
    subject: str = Field(min_length=1)
    determination: Determination
    risk_level: RiskLevel
    summary: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    legal_sources: list[PublicLegalSourceDto] = Field(default_factory=list)


class PublicToolReviewDto(ApiModel):
    """분야 카드. agent_type·status는 BE AgentType·AgentReviewStatus 값."""

    agent_type: Literal["CUSTOMS", "CHILDREN", "ELECTRICAL", "RADIO", "FOOD_DRUG", "LABEL_AD"]
    status: Literal["COMPLETED", "SKIPPED", "INCOMPLETE"]
    message: str | None = None
    findings: list[PublicFindingDto] = Field(default_factory=list)


class PublicAssessmentDto(ApiModel):
    """공개 진단서. result_status는 BE ResultStatus 값."""

    status: Literal["completed", "incomplete"]
    result_status: Literal[
        "PURCHASING_AGENT_ALLOWED",
        "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
        "RECHECK_REQUIRED",
    ]
    summary: str = Field(min_length=1)
    tool_reviews: list[PublicToolReviewDto] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_display_state(self):
        if self.status == "incomplete" and not self.notices:
            raise ValueError("미완료 결과에는 공개 안내가 필요합니다.")
        if self.status == "incomplete" and self.result_status != "RECHECK_REQUIRED":
            raise ValueError("미완료 결과는 재확인 필요로만 냅니다.")
        names = [review.agent_type for review in self.tool_reviews]
        if len(names) != len(set(names)):
            raise ValueError("같은 분야의 검토 카드를 중복 전달하지 않습니다.")
        return self


class ProductResultEvent(ProductEventBase):
    """결과 콜백. 이 실행의 마지막, 진단서 포함."""

    event_type: Literal["product_result"] = "product_result"
    assessment: PublicAssessmentDto


class PublicErrorDto(ApiModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool | None = None


class ProductFailedEvent(ProductEventBase):
    """실패 콜백. 이 실행의 마지막."""

    event_type: Literal["product_failed"] = "product_failed"
    stage: PublicPipelineStage | None = None
    error: PublicErrorDto


PublicProductEvent = Annotated[
    ProductProgressEvent | ProductAwaitingInputEvent | ProductResultEvent | ProductFailedEvent,
    Field(discriminator="event_type"),
]
