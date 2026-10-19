"""에이전트 공통 타입. 주입 모델의 최소 인터페이스(BaseChatModel·테스트 스텁 모두 만족)와 제네릭 타입 변수."""

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredModel(Protocol):
    """``with_structured_output(..., include_raw=True)``가 돌려주는 객체."""

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        """모델을 호출한다.

        Args:
            messages: 모델에 보낼 메시지.

        Returns:
            dict[str, Any]: ``{"raw": AIMessage, "parsed": 출력 | None, "parsing_error": Exception | None}``.
        """
        ...


class ModelLike(Protocol):
    """에이전트가 받는 채팅 모델."""

    def with_structured_output(self, schema: dict[str, Any], **kwargs: Any) -> StructuredModel:
        """구조화 출력 모델을 만든다.

        Args:
            schema: 출력 JSON 스키마.
            **kwargs: include_raw·strict 등 옵션.

        Returns:
            StructuredModel: 구조화 출력 모델.
        """
        ...
