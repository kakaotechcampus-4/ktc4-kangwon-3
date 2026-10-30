"""표시·광고 Tool 예외."""

from ...agents.base import AgentError


class AdvertisingReviewError(AgentError):
    """표시·광고 문구 검토 모델 호출 또는 파싱 실패."""
