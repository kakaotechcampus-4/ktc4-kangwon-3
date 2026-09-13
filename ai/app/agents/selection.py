"""선택 담당자가 구현할 에이전트 뼈대."""

from ..schemas.agent import SelectionResult
from ..schemas.product import Product


class SelectionAgent:
    """상품 정보를 보고 필요한 심사 툴을 선택하고 실행한다."""

    def select(self, product: Product) -> SelectionResult:
        """
        입력: 추출 에이전트가 만든 Product
        출력: 툴 선택 내역과 실제 실행 결과를 담은 SelectionResult
        """
        # TODO: LangChain 모델·selection 프롬프트·6개 @tool 연결
        # TODO: 필요한 툴 선택·실행 (선택 목록과 실제 실행 내역 구분)
        # TODO: 미선택 사유와 실행 이력을 포함한 SelectionResult 반환
        raise NotImplementedError("선택 담당자가 구현할 예정입니다.")
