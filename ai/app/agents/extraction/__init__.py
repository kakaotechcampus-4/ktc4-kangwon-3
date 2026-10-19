"""추출 에이전트 패키지.

- agent.py: ExtractionAgent — 상품 원문 → Product (모델 추출 + 규칙 추출 병합)
- rules.py: 정규식 기반 속성·충돌 추출 (모델과 독립)
- seller_region.py: 쇼핑몰이 붙인 글을 잘라 판매자 영역만 남김
- prompt.md: 시스템 프롬프트
"""

from .agent import PROMPT_PATH, ExtractionAgent, ExtractionFailedError

__all__ = ["PROMPT_PATH", "ExtractionAgent", "ExtractionFailedError"]
