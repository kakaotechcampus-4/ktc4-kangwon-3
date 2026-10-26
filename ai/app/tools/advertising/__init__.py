"""표시·광고 Tool 패키지.

- tool.py: 흐름(문구 검토 → 인용 대조 → KC 표기 보충 → 결과 조립)
- steps.py: 모델 호출 단계(판매자 문구 검토, AdvertisingReviewer)
- rules.py: 근거 조문, KC 표기 찾기, 위험도·할 일 문구
- errors.py: AdvertisingReviewError
"""

from .errors import AdvertisingReviewError
from .steps import AdvertisingReviewer
from .tool import AdvertisingTool

__all__ = ["AdvertisingReviewError", "AdvertisingReviewer", "AdvertisingTool"]
