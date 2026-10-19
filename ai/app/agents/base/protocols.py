"""에이전트가 받는 모델 객체의 최소 인터페이스. 실제 모델(BaseChatModel)과 테스트 스텁 모두 만족."""

from typing import Any, Protocol


class StructuredModel(Protocol):
    """``with_structured_output(..., include_raw=True)``가 돌려주는 객체의 최소 인터페이스.

    invoke()는 ``{"raw": AIMessage, "parsed": 출력 | None, "parsing_error": Exception | None}``을 돌려줌.
    """

    def invoke(self, messages: list[Any]) -> dict[str, Any]: ...


class ModelLike(Protocol):
    """에이전트가 받는 모델의 최소 인터페이스.

    ``BaseChatModel``과 테스트 스텁 모두 이 구조를 만족함.
    """

    def with_structured_output(self, schema: dict[str, Any], **kwargs: Any) -> StructuredModel: ...
