"""6개 심사 결과를 검증용 초안으로 종합하는 도구. 별도의 에이전트가 아니다."""

from ..schemas.product import Product
from ..schemas.schemas import DraftAssessment, ToolResult


class ResultAggregationTool:
    def run(self, product: Product, tool_results: list[ToolResult]) -> DraftAssessment:
        """상품 정보, 선택·미선택 내역, 실행 결과 및 근거를 종합한다."""
        # TODO: 선택된 툴의 실행이 끝난 후 결과를 종합한다. 미선택 기록도 유지한다.
        # 없는 법적 근거를 생성하거나 조회 실패를 정상 결과로 덮어쓰지 않는다.
        raise NotImplementedError("결과 종합 로직은 아직 구현되지 않았습니다.")
