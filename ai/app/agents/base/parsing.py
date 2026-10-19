"""구조화 출력 모델 응답을 출력 스키마로 해석한다."""

from typing import Any, TypeVar

from langchain_openai.chat_models.base import OpenAIRefusalError
from pydantic import BaseModel

from .errors import MissingParsedOutput

OutputT = TypeVar("OutputT", bound=BaseModel)


def parse_structured_output(result: dict[str, Any], output_schema: type[OutputT], component_name: str) -> OutputT:
    """구조화 출력 결과를 출력 스키마로 검증한다. 본문은 엄격한 JSON으로, 본문이 없으면 parsed(테스트 스텁)로.

    Args:
        result: ``StructuredModel.invoke`` 결과 ``{"raw", "parsed", "parsing_error"}``.
        output_schema: 출력 스키마.
        component_name: 오류 문구에 쓸 에이전트 이름.

    Returns:
        OutputT: 검증된 출력.

    Raises:
        OpenAIRefusalError: 모델이 거절한 경우.
        ValidationError: JSON 오류·스키마 위반.
        MissingParsedOutput: 본문도 parsed도 없는 경우.
        Exception: 본문 없는 응답의 parsing_error를 그대로 던짐.
    """
    raw_message = result.get("raw")
    refusal = (getattr(raw_message, "additional_kwargs", None) or {}).get("refusal")
    # 응답에 refusal이 있음 (모델이 답변 거절)
    if refusal:
        raise OpenAIRefusalError(refusal)
    content = getattr(raw_message, "content", None)
    # 본문이 있으면 엄격한 JSON 검증. LangChain parsed(잘린 JSON 보정 등 관대한 해석)는 안 씀
    if isinstance(content, str) and content.strip():
        return output_schema.model_validate_json(content)

    # 여기부터 본문 없음 (빈 응답 또는 parsed를 바로 주는 테스트 스텁)
    parsing_error = result.get("parsing_error")
    # LangChain이 파싱 오류를 넘긴 경우. 예외 객체면 그대로, 문자열이면 감싸서
    if parsing_error is not None:
        if isinstance(parsing_error, Exception):
            raise parsing_error
        raise MissingParsedOutput(f"{component_name}: 구조화 출력 파싱 실패: {parsing_error}")
    parsed = result.get("parsed")
    # 본문·parsed·오류 모두 없음 (빈 출력)
    if parsed is None:
        raise MissingParsedOutput(f"{component_name}: 구조화 출력이 비어 있습니다.")
    return output_schema.model_validate(parsed)
