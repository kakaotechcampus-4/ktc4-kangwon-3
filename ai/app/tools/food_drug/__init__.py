"""식약 Tool 패키지 (식품용 기구·식품·화장품·의료기기).

- tool.py: 흐름(조건 추출 → 영역별 규칙 → 의료기기 품목 조회 → 품목 선택 → 결과 조립)
- rules.py: 판매 방식별 안내 문구
- search.py: 근거 캐시와 의료기기 품목 순위
- evidence.py: 식품·화장품·의료기기 법령 조문, 의료기기 품목·등급 별표, 화장품 금지 원료 별표
"""

from .tool import FoodDrugTool, FoodDrugToolError

__all__ = ["FoodDrugTool", "FoodDrugToolError"]
