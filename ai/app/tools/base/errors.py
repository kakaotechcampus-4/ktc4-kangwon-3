"""규제 Tool 공통 예외."""

from ...agents.base import AgentError


class ToolModelError(AgentError):
    """규제 Tool의 모델 호출·구조화 출력 실패. 원인은 예외 체인에 보존한다."""
