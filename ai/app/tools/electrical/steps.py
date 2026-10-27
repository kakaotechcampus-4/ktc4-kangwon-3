"""전기안전 Tool의 모델 호출 단계: 조건 추출, 품목 선택."""

from ...prompts import PromptName
from ...schemas.electrical import ElectricalFacts, ElectricalReview
from ..base import ToolStep
from .errors import ElectricalToolError


class ElectricalFactsStep(ToolStep[ElectricalFacts]):
    component_name = "electrical-facts"
    prompt_name = PromptName.ELECTRICAL_FACTS
    output_schema = ElectricalFacts
    error_class = ElectricalToolError
    failure_label = "전기 Tool 조건 추출"


class ElectricalReviewStep(ToolStep[ElectricalReview]):
    component_name = "electrical-review"
    prompt_name = PromptName.ELECTRICAL_REVIEW
    output_schema = ElectricalReview
    error_class = ElectricalToolError
    failure_label = "전기 Tool 품목 선택"
