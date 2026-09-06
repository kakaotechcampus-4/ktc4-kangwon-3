"""심사 툴 결과, 종합 결과 및 검증 스키마.

공통·상품 모델은 base.py와 product.py에서 정의한다.
기존 호출부의 ``from .schemas import Product`` 형식도 유지한다.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import Field

# 재노출: 기존 from .schemas import Product 등의 호출부가 같은 모델에 접근하게 한다.
from .base import StrictModel as StrictModel, utc_now as utc_now
from .product import Attribute as Attribute, Product as Product


# 선택·실행·검증 단계에서 공유하는 심사 툴 식별자. 결과 종합 툴은 이 목록과 별개이다.
class ToolName(StrEnum):
    CUSTOMS = "customs_requirements"
    RADIO = "radio_compliance"
    FOOD_DRUG = "food_drug_safety"
    ELECTRICAL = "electrical_safety"
    CHILDREN = "children_product_safety"
    LABEL_AD = "labeling_advertising_detection"


# 실행 상태이다. SUCCESS는 실행 성공이지 규제 심사 통과를 뜻하지 않는다.
# 현재 프로토타입은 미선택 툴에도 NOT_APPLICABLE을 쓰므로 규제 비대상 확정과 구분해야 한다.
class ToolStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


# 개별 항목의 심사 판단. 실행 오류와 판단에 필요한 정보 부족을 구분해서 사용한다.
class Determination(StrEnum):
    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    POSSIBLY_REQUIRED = "possibly_required"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NOT_APPLICABLE = "not_applicable"


# UNKNOWN은 낮은 위험이 아니라 위험 수준을 판단하지 못한 상태이다.
class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


# 종합 판단의 요약 상태. LIKELY_COMPLIANT도 법적 적합성을 보증하는 승인은 아니다.
class OverallStatus(StrEnum):
    LIKELY_COMPLIANT = "likely_compliant"
    ACTION_REQUIRED = "action_required"
    HIGH_RISK = "high_risk"
    INSUFFICIENT_INFORMATION = "insufficient_information"


# 판단에 사용한 법령·기관 자료. 실제 조회한 내용과 확인 가능한 출처를 기록한다.
# is_mock=True가 기본값이므로 실조회 자료와 예시 자료를 구분해 설정해야 한다.
# effective_date는 현재 자유 문자열이며, 날짜 형식·현행 여부를 자동 검사하지 않는다.
class LegalSource(StrictModel):
    source_name: str
    law_name: str | None = None
    article: str | None = None
    quoted_text: str | None = None
    source_url: str | None = None
    effective_date: str | None = None
    is_mock: bool = True


# 통관 심사의 상세 결과. HS 후보 목록은 확정된 품목분류와 다르다.
class CustomsAssessment(StrictModel):
    kind: Literal["customs"] = "customs"
    hs_code_candidates: list[str] = Field(default_factory=list)
    customs_confirmation_required: bool | None = None
    applicable_requirements: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    legal_sources: list[LegalSource] = Field(default_factory=list)


# 통신 기능·주파수와 적합성평가 필요 여부에 대한 심사 결과.
class RadioAssessment(StrictModel):
    kind: Literal["radio"] = "radio"
    wireless_features: list[str] = Field(default_factory=list)
    frequency_bands: list[str] = Field(default_factory=list)
    conformity_assessment_required: bool | None = None
    certification_type: str | None = None
    legal_sources: list[LegalSource] = Field(default_factory=list)


# 식약 관련 분류, 표방 문구, 성분·재질과 확인한 요건을 담는다.
class FoodDrugAssessment(StrictModel):
    kind: Literal["food_drug"] = "food_drug"
    regulatory_categories: list[str] = Field(default_factory=list)
    regulated: bool | None = None
    detected_claims: list[str] = Field(default_factory=list)
    ingredients_or_materials: list[str] = Field(default_factory=list)
    applicable_requirements: list[str] = Field(default_factory=list)
    legal_sources: list[LegalSource] = Field(default_factory=list)


# 전원·정격 등 상품 특성과 안전관리 필요 여부에 대한 심사 결과.
class ElectricalAssessment(StrictModel):
    kind: Literal["electrical"] = "electrical"
    power_sources: list[str] = Field(default_factory=list)
    rated_specifications: list[str] = Field(default_factory=list)
    safety_management_required: bool | None = None
    certification_type: str | None = None
    legal_sources: list[LegalSource] = Field(default_factory=list)


# 표시 연령 원문과 어린이 대상 여부에 대한 해석을 분리해 기록한다.
class ChildrenAssessment(StrictModel):
    kind: Literal["children"] = "children"
    target_age_raw: str | None = None
    intended_for_children: bool | None = None
    product_type: str | None = None
    safety_management_required: bool | None = None
    certification_type: str | None = None
    legal_sources: list[LegalSource] = Field(default_factory=list)


# 문제 가능성이 발견된 문구 하나와 그 사유. 실제 위반 확정을 뜻하지 않는다.
class AdvertisingPhrase(StrictModel):
    text: str
    risk_type: str
    risk_level: RiskLevel
    reason: str
    evidence_required: bool = False


# 검토한 문구 전체와 그중 주의가 필요한 문구를 분리한다.
# detected_phrases가 비어 있어도 검토 범위 밖까지 안전하다는 뜻은 아니다.
class AdvertisingAssessment(StrictModel):
    kind: Literal["advertising"] = "advertising"
    reviewed_phrases: list[str] = Field(default_factory=list)
    detected_phrases: list[AdvertisingPhrase] = Field(default_factory=list)
    overall_risk: RiskLevel
    legal_sources: list[LegalSource] = Field(default_factory=list)


# kind 값으로 상세 결과 모델을 고르는 판별 유니온이다.
# 예: kind="radio"인 JSON은 RadioAssessment로 검증한다.
# ToolResult.tool_name과 kind의 일치 여부까지 자동으로 검사하는 선언은 아니다.
ToolAssessment = Annotated[
    CustomsAssessment
    | RadioAssessment
    | FoodDrugAssessment
    | ElectricalAssessment
    | ChildrenAssessment
    | AdvertisingAssessment,
    Field(discriminator="kind"),
]


# 상세 결과를 여러 툴에 걸쳐 종합·검증할 수 있게 표현한 공통 판단 항목.
# 툴 하나가 여러 항목을 만들 수 있으며 finding_id로 검증 지적과 연결한다.
# product_facts_used는 사용한 사실, assumptions는 확인하지 못한 가정이다.
# confidence는 0~1 범위만 검사하며 실제 정확도를 보증하지 않는다.
class RegulatoryFinding(StrictModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: ToolName
    subject: str
    determination: Determination
    risk_level: RiskLevel
    summary: str
    rationale: str
    product_facts_used: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    legal_sources: list[LegalSource] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)

# 규제 툴 하나의 실행 결과
# 실행 정보와 심사 내용을 함께 전달하는 공통 형식.
# result는 심사별 상세 내용, findings는 여러 툴을 함께 종합할 때 사용하는 공통 판단이다.
# query와 raw_response에 API 키·토큰·개인정보를 저장하거나 그대로 외부 전달하지 않는다.
class ToolResult(StrictModel):
    tool_name: ToolName
    status: ToolStatus
    selected: bool
    selection_reason: str
    query: dict[str, Any] = Field(default_factory=dict)
    result: ToolAssessment | None = None
    findings: list[RegulatoryFinding] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    raw_response: dict[str, Any] | list[Any] | str | None = None
    error: str | None = None
    executed_at: datetime = Field(default_factory=utc_now)


# 자동으로 확인할 수 없는 상품 정보에 대해 사용자에게 추가로 물어볼 질문.
class FollowUpQuestion(StrictModel):
    question_id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    reason: str
    related_tools: list[ToolName] = Field(default_factory=list)
    required: bool = True


# 실행 순서와 상태를 추적하는 기록. 내부 추론 대신 실행 사실·결과를 남긴다.
class TraceEvent(StrictModel):
    sequence: int
    stage: str
    component: str
    action: str
    status: str
    detail: str
    created_at: datetime = Field(default_factory=utc_now)

# 여러 툴의 결과를 합친 검증 전 초안
# 검증 에이전트의 입력. 아직 검증 전이므로 최종 응답과 구분한다.
class DraftAssessment(StrictModel):
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    product: Product
    selected_tools: list[ToolName]
    tool_results: list[ToolResult]
    findings: list[RegulatoryFinding]
    overall_status: OverallStatus
    summary: str
    required_actions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


# 검증 중 발견한 문제의 분류. 툴 누락·조회 실패·근거 부족 등을 구분한다.
class VerificationIssueType(StrEnum):
    MISSING_TOOL = "missing_tool"
    TOOL_FAILURE = "tool_failure"
    MISSING_EVIDENCE = "missing_evidence"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CONTRADICTION = "contradiction"
    INSUFFICIENT_PRODUCT_DATA = "insufficient_product_data"
    INCORRECT_DETERMINATION = "incorrect_determination"


# 지적 사항 하나. related_finding_ids는 문제가 있는 원래 판단 항목을 가리킨다.
# severity는 자유 문자열이므로 실행부의 critical 등과 표기를 맞춰야 한다.
# recommended_action은 설명용 문구이며, 자체적으로 재실행을 수행하지 않는다.
class VerificationIssue(StrictModel):
    issue_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: str
    issue_type: VerificationIssueType
    description: str
    related_finding_ids: list[str] = Field(default_factory=list)
    recommended_action: str | None = None


# 검증 후 다음 단계의 판단. 실제 분기와 재시도 제한은 파이프라인의 책임이다.
# REVISION_REQUIRED는 보완 필요, USER_INPUT_REQUIRED는 사용자 답변이 필요한 상태이다.
class VerificationStatus(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REVISION_REQUIRED = "revision_required"
    USER_INPUT_REQUIRED = "user_input_required"


# 검증 결과와 후속 요청. additional_tools_required는 추가·재실행할 툴 목록이다.
# checked_finding_ids에는 실제로 검토한 판단 항목의 식별자를 기록한다.
# 추출 단계로 되돌리는 전용 요청 필드는 아직 없는 초안이다.
class VerificationResult(StrictModel):
    status: VerificationStatus
    review_summary: str | None = None
    issues: list[VerificationIssue] = Field(default_factory=list)
    additional_tools_required: list[ToolName] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)
    checked_finding_ids: list[str] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=utc_now)


# VERIFIED는 내부 검증 완료이지 기관 인증이 아니다. INCOMPLETE는 미완료 상태이다.
class FinalVerificationStatus(StrEnum):
    VERIFIED = "verified"
    VERIFIED_WITH_WARNINGS = "verified_with_warnings"
    INCOMPLETE = "incomplete"

# 검증 결과까지 포함한 최종 결과
# 최종 응답이라도 INCOMPLETE일 수 있다. 검증 완료 여부와 종합 판단을 함께 확인한다.
# schema_version은 소비자가 데이터 규격을 구분하기 위한 문자열이다.
# 현재 초안에는 재검사 이력 필드가 없어 기존 재검사 파이프라인과 정합성 확인이 필요하다.
class FinalAssessment(StrictModel):
    assessment_id: str
    schema_version: str = "0.2.0"
    product: Product
    verification_status: FinalVerificationStatus
    overall_status: OverallStatus
    summary: str
    selected_tools: list[ToolName]
    tool_results: list[ToolResult]
    findings: list[RegulatoryFinding]
    required_actions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)
    verification: VerificationResult
    trace: list[TraceEvent] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

