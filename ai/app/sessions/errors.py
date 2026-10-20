"""세션 접수 거절 오류. 라우터가 HTTP 응답(409·429)으로 바꿈."""


class QueueFullError(RuntimeError):
    """대기 + 실행 중 세션이 상한을 넘어 접수를 거절한 경우."""


class SessionConflictError(RuntimeError):
    """진행 중인 상품이 요청에 섞여 있어 접수를 거절한 경우.

    Attributes:
        product_ids: 이미 진행 중인 상품 ID 목록.
    """

    def __init__(self, product_ids: list[str]) -> None:
        super().__init__(f"이미 진행 중인 상품이 있습니다: {', '.join(product_ids)}")
        self.product_ids = product_ids
