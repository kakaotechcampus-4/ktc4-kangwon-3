"""판단 클라이언트 예외."""

from ...errors import ClientError


class DecisionResponseError(ClientError, ValueError):
    """판단 응답을 공통 모양으로 바꿀 수 없는 경우 (JSON 아님·필드 누락·질문 답 누락)."""
