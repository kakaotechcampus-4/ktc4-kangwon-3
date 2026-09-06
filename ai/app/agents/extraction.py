"""추출 담당자가 구현할 에이전트 뼈대."""

from ..schemas.agent import ExtractionInput
from ..schemas.product import Product


class ExtractionAgent:
    """상품 원문에서 정보를 추출한다. 툴 선택이나 규제 판정은 맡지 않는다."""

    def extract(self, source: ExtractionInput) -> Product:
        """
        입력: 수집된 상품 텍스트·이미지 참조
        출력: 상품 정보와 15개 툴 선택 신호를 담은 Product
        """
        # TODO: LangChain 모델과 extraction 프롬프트 연결
        # TODO: 원문에서 상품 정보 추출 (정보 부족은 None, 연령은 원문 유지)
        # TODO: 요청의 상품 식별자·출처를 유지한 Product 반환
        raise NotImplementedError("추출 담당자가 구현할 예정입니다.")
