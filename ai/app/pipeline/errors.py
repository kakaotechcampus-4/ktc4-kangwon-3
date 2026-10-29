"""파이프라인 예외."""

from ..domain.errors import AIError


class UnsupportedSiteError(AIError, ValueError):
    """수집할 수 없는 판매 사이트 주소."""
