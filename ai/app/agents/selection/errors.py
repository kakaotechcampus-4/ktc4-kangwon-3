"""선택 에이전트 예외."""

from ..base import AgentError


class SelectionFailedError(AgentError):
    """선택 모델 호출·파싱 실패. 원인 예외는 ``__cause__``."""
