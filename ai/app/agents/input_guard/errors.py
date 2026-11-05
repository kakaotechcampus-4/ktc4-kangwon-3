"""입력 가드 예외."""

from ..base import AgentError


class InputGuardFailedError(AgentError):
    """판단 모델 호출·응답 변환 실패. 원인 예외는 ``__cause__``. 가드는 실패를 통과로 처리 (fail-open)."""
