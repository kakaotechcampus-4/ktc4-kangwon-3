"""AI → BE 진단 콜백 이벤트와 공개 진단서 스키마 (#301, #310).

콜백 수신 경로: POST /internal/v1/ai/products/{productId} (#263). 이벤트 종류는 eventType 하나로 구분.
질문·결과·실패 이벤트는 그 실행(runId)의 마지막 이벤트.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ApiModel
from .schemas import Determination, RiskLevel


# BE에 공개하는 분야 이름 (#310 2026-10-15 추가). 진행 콜백·분야 카드가 같이 씀
# BE AgentType과 같은 값 (#325에서 ToolName으로 이름 변경)
PublicToolName = Literal["CUSTOMS", "CHILDREN", "ELECTRICAL", "RADIO", "FOOD_DRUG", "LABEL_AD"]

# 공백 아닌 글자가 하나 이상 (BE @NotBlank). 공백뿐이면 BE가 400으로 거절해 결과가 사라짐
NonBlankStr = Annotated[str, Field(pattern=r"\S")]


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

    event_id: NonBlankStr
    diagnosis_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    run_id: NonBlankStr
    sequence: int = Field(ge=1, strict=True)


class ProductProgressEvent(ProductEventBase):
    """진행 콜백. BE는 저장하지 않고 화면 표시에만 씀."""

    event_type: Literal["product_progress"] = "product_progress"
    stage: PublicPipelineStage
    stage_status: Literal["started", "completed", "skipped"]
    tool_name: PublicToolName | None = None

    @model_validator(mode="after")
    def validate_tool_stage(self):
        if self.tool_name is not None and self.stage is not PublicPipelineStage.TOOL_EXECUTION:
            raise ValueError("tool_name은 Tool 실행 단계에서만 전달합니다.")
        return self


class PublicQuestionDto(ApiModel):
    """사용자에게 물을 질문 하나. BE ProductQuestion 저장 형식."""

    question_key: NonBlankStr = Field(max_length=50)
    question_order: int = Field(ge=1, strict=True)
    question_text: NonBlankStr
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


# 최대 길이는 BE 수신 DTO(#331)·DB 칸 길이와 같음. 넘으면 BE가 400으로 거절해 결과가 사라짐
class PublicLegalSourceDto(ApiModel):
    source_name: NonBlankStr = Field(max_length=255)
    law_name: str | None = Field(default=None, max_length=255)
    article: str | None = Field(default=None, max_length=255)
    quoted_text: str | None = None
    source_url: str | None = None
    effective_date: str | None = Field(default=None, max_length=50)


class PublicFindingDto(ApiModel):
    subject: NonBlankStr = Field(max_length=255)
    determination: Determination
    risk_level: RiskLevel
    summary: NonBlankStr
    rationale: NonBlankStr
    legal_sources: list[PublicLegalSourceDto] = Field(default_factory=list)


class PublicToolReviewDto(ApiModel):
    """분야 카드. tool_name·status는 BE ToolName·ToolReviewStatus 값."""

    tool_name: PublicToolName
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
    summary: NonBlankStr
    tool_reviews: list[PublicToolReviewDto] = Field(default_factory=list)
    required_actions: list[NonBlankStr] = Field(default_factory=list)
    notices: list[NonBlankStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_display_state(self):
        if self.status == "incomplete" and not self.notices:
            raise ValueError("미완료 결과에는 공개 안내가 필요합니다.")
        if self.status == "incomplete" and self.result_status != "RECHECK_REQUIRED":
            raise ValueError("미완료 결과는 재확인 필요로만 냅니다.")
        names = [review.tool_name for review in self.tool_reviews]
        if len(names) != len(set(names)):
            raise ValueError("같은 분야의 검토 카드를 중복 전달하지 않습니다.")
        return self


class ProductResultEvent(ProductEventBase):
    """결과 콜백. 이 실행의 마지막, 진단서 포함."""

    event_type: Literal["product_result"] = "product_result"
    assessment: PublicAssessmentDto


class PublicErrorDto(ApiModel):
    code: NonBlankStr = Field(max_length=50)  # BE Product.error_code 칸 길이
    message: NonBlankStr
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
