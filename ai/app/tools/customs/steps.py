"""통관 요건 Tool의 모델 호출 단계: 조건 추출, 결정사례 선택."""

from ...prompts import PromptName
from ...schemas.customs import CustomsFacts, CustomsReview
from ..base import ToolStep
from .errors import CustomsToolError


class CustomsFactsStep(ToolStep[CustomsFacts]):
    component_name = "customs-facts"
    prompt_name = PromptName.CUSTOMS_FACTS
    output_schema = CustomsFacts
    error_class = CustomsToolError
    failure_label = "통관 Tool 조건 추출"


class CustomsReviewStep(ToolStep[CustomsReview]):
    component_name = "customs-review"
    prompt_name = PromptName.CUSTOMS_REVIEW
    output_schema = CustomsReview
    error_class = CustomsToolError
    failure_label = "통관 Tool 결정사례 선택"
