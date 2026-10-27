"""전파 Tool의 모델 호출 단계: 조건 추출, 기자재 선택."""

from ...prompts import PromptName
from ...schemas.radio import RadioFacts, RadioReview
from ..base import ToolStep
from .errors import RadioToolError


class RadioFactsStep(ToolStep[RadioFacts]):
    component_name = "radio-facts"
    prompt_name = PromptName.RADIO_FACTS
    output_schema = RadioFacts
    error_class = RadioToolError
    failure_label = "전파 Tool 조건 추출"


class RadioReviewStep(ToolStep[RadioReview]):
    component_name = "radio-review"
    prompt_name = PromptName.RADIO_REVIEW
    output_schema = RadioReview
    error_class = RadioToolError
    failure_label = "전파 Tool 기자재 선택"
