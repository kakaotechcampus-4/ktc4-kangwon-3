"""표시·광고 Tool 예외."""

from ...agents.base import AgentError


class AdvertisingReviewError(AgentError):
    """표시·광고 문구 검토 모델 호출 또는 파싱 실패."""


class AdvertisingEvidenceError(AgentError):
    """적용 판 근거 조문을 읽지 못함. 원본 오류는 예외 체인에만 보존함."""
