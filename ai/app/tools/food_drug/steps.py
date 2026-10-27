"""식약 Tool의 모델 호출 단계: 조건 추출, 의료기기 품목 선택."""

from ...prompts import PromptName
from ...schemas.food_drug import DeviceReview, FoodDrugFacts
from ..base import ToolStep
from .errors import FoodDrugToolError


class FoodDrugFactsStep(ToolStep[FoodDrugFacts]):
    component_name = "food-drug-facts"
    prompt_name = PromptName.FOOD_DRUG_FACTS
    output_schema = FoodDrugFacts
    error_class = FoodDrugToolError
    failure_label = "식약 Tool 조건 추출"


class FoodDrugReviewStep(ToolStep[DeviceReview]):
    component_name = "food-drug-review"
    prompt_name = PromptName.FOOD_DRUG_REVIEW
    output_schema = DeviceReview
    error_class = FoodDrugToolError
    failure_label = "식약 Tool 의료기기 품목 선택"
