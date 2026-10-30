"""판단 선택 에이전트 예외."""

from ..base import AgentError


class DecisionSelectionFailedError(AgentError):
    """판단 모델 호출·응답 변환 실패. 원인 예외는 ``__cause__``."""
