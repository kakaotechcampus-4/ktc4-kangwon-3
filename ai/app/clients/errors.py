"""외부 API·판매 사이트 클라이언트 공통 예외."""

from ..domain.errors import AIError


class ClientError(AIError):
    """클라이언트 예외의 공통 부모."""
