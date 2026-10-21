"""세션 예외.

    - 접수·재진단 거절: 라우터가 HTTP 응답(400·404·409·422·429)으로 바꿈
    - 전이 오류(InvalidTransitionError): 세션 관리자가 경고 로그만 남기고 무시
"""

from typing import TYPE_CHECKING

from ..domain.errors import AIError
from ..schemas.session import SessionStatus

if TYPE_CHECKING:
    from .transitions import Change


class SessionError(AIError):
    """세션 예외의 공통 부모."""


class QueueFullError(SessionError, RuntimeError):
    """대기 + 실행 중 세션이 상한을 넘어 접수를 거절한 경우."""


class SessionConflictError(SessionError, RuntimeError):
    """진행 중인 상품이 요청에 섞여 있어 접수를 거절한 경우.

    Attributes:
        product_ids: 이미 진행 중인 상품 ID 목록.
    """

    def __init__(self, product_ids: list[str]) -> None:
        super().__init__(f"이미 진행 중인 상품이 있습니다: {', '.join(product_ids)}")
        self.product_ids = product_ids


class SessionNotFoundError(SessionError, LookupError):
    """재진단할 세션이 없는 경우. AI 재시작·정리로 사라진 세션 포함."""


class ResumeConflictError(SessionError, RuntimeError):
    """답변 대기가 아니거나, 요청이 기다리는 질문(실행·회차·진단서)과 맞지 않는 경우. 중복·늦게 온 답변."""


class UnknownQuestionKeyError(SessionError, ValueError):
    """이번 회차에 묻지 않은 질문의 답변이 섞인 경우.

    Attributes:
        question_keys: 묻지 않은 질문 키 목록.
    """

    def __init__(self, question_keys: list[str]) -> None:
        super().__init__(f"이번 회차에 묻지 않은 질문입니다: {', '.join(question_keys)}")
        self.question_keys = question_keys


class UnansweredQuestionError(SessionError, ValueError):
    """이번 회차 질문 중 답하지 않은 질문이 있는 경우. BE 답변 제출과 같은 기준.

    Attributes:
        question_keys: 답하지 않은 질문 키 목록.
    """

    def __init__(self, question_keys: list[str]) -> None:
        super().__init__(f"답하지 않은 질문이 있습니다: {', '.join(question_keys)}")
        self.question_keys = question_keys


class InvalidTransitionError(SessionError, ValueError):
    """규칙표에 없는 전이를 요청한 경우. 시간 초과 뒤 늦게 온 결과 등.

    Attributes:
        status: 세션의 지금 상태.
        change: 요청한 일.
    """

    def __init__(self, status: SessionStatus, change: "Change") -> None:
        super().__init__(f"{status} 상태에서는 {type(change).__name__}을 할 수 없습니다.")
        self.status = status
        self.change = change
