"""어린이제품 Tool의 모델 호출 단계: 조건 추출, 품목 선택."""

from ...prompts import PromptName
from ...schemas.children import ChildrenFacts, ChildrenReview
from ..base import ToolStep
from .errors import ChildrenToolError


class ChildrenFactsStep(ToolStep[ChildrenFacts]):
    component_name = "children-facts"
    prompt_name = PromptName.CHILDREN_FACTS
    output_schema = ChildrenFacts
    error_class = ChildrenToolError
    failure_label = "어린이제품 Tool 조건 추출"


class ChildrenReviewStep(ToolStep[ChildrenReview]):
    component_name = "children-review"
    prompt_name = PromptName.CHILDREN_REVIEW
    output_schema = ChildrenReview
    error_class = ChildrenToolError
    failure_label = "어린이제품 Tool 품목 선택"
