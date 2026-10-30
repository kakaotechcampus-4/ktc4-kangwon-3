"""판단 클라이언트 예외."""

from ....schemas.clients.decision_response import DecisionUsage
from ...errors import ClientError


class DecisionRequestError(ClientError, ValueError):
    """제공사 형식으로 보낼 수 없는 판단 요청 (질문 이름·후보 값 중복). 요청은 보내지 않음."""


class DecisionResponseError(ClientError, ValueError):
    """판단 응답을 공통 모양으로 바꿀 수 없는 경우 (JSON 아님·필드 누락·질문 답 누락).

    Attributes:
        usage: 응답에서 읽은 모델·토큰 사용량. 사용량까지 못 읽었으면 None.
    """

    def __init__(self, message: str, *, usage: DecisionUsage | None = None) -> None:
        """예외를 만든다.

        Args:
            message: 예외 메시지.
            usage: 응답에서 읽은 모델·토큰 사용량.
        """
        super().__init__(message)
        self.usage = usage
