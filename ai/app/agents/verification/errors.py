"""검증 에이전트 예외."""

from ..base import AgentError


class VerificationError(AgentError):
    """모델 검증 미완료. ``partial_result``는 규칙 검사 결과(VerificationResult).

    파이프라인은 이를 ``FinalVerificationStatus.INCOMPLETE``로 처리하고 검증 완료로 보지 않아야 함.
    """
