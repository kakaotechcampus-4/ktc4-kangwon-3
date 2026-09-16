"""6개 심사 결과를 검증용 초안으로 종합하는 도구. 별도의 에이전트가 아니다."""

from ..schemas.product import Product
from ..schemas.schemas import DraftAssessment, ToolResult


class ResultAggregator:
    def run(self, product: Product, selection_results: list[ToolResult]) -> DraftAssessment:

        raise NotImplementedError("결과 종합 로직은 아직 구현되지 않았습니다.")
