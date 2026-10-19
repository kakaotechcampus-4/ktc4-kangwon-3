"""구조화 출력 모델 응답을 출력 스키마로 해석한다. 응답을 다 받은 뒤 실행돼 사용량은 이미 남아 있음."""

from typing import Any, TypeVar

from langchain_openai.chat_models.base import OpenAIRefusalError
from pydantic import BaseModel

from .errors import MissingParsedOutput

OutputT = TypeVar("OutputT", bound=BaseModel)


def parse_structured_output(result: dict[str, Any], output_schema: type[OutputT], component_name: str) -> OutputT:
    """구조화 출력 결과를 출력 스키마로 검증한다.

    본문이 있으면 엄격한 JSON으로 검증하고, 본문이 없으면 parsed(테스트 스텁)를 씀.

    Args:
        result: ``with_structured_output(include_raw=True)``의 ``{"raw", "parsed", "parsing_error"}``.
        output_schema: 검증할 출력 스키마.
        component_name: 오류 문구에 쓸 에이전트 이름.

    Returns:
        OutputT: 검증된 출력.

    Raises:
        Exception: JSON 오류·스키마·검증 함수 위반(ValidationError), 모델 거절(OpenAIRefusalError),
            본문 없는 응답의 파싱 오류(parsing_error 그대로), 출력 누락(MissingParsedOutput).
    """
    raw_message = result.get("raw")
    # 모델이 거절한 경우. develop(SDK 파싱)과 같은 원인 예외 사용
    refusal = (getattr(raw_message, "additional_kwargs", None) or {}).get("refusal")
    if refusal:
        raise OpenAIRefusalError(refusal)
    content = getattr(raw_message, "content", None)
    if isinstance(content, str) and content.strip():
        # 본문은 엄격한 JSON으로 검증 (SDK와 같은 pydantic JSON 모드).
        # LangChain 파서의 parsed는 잘린 JSON 보정·코드블록 제거 등 관대하게 해석해 쓰지 않음
        return output_schema.model_validate_json(content)

    # 본문이 없는 응답(빈 응답) 또는 parsed를 바로 주는 테스트 스텁
    parsing_error = result.get("parsing_error")
    if parsing_error is not None:
        if isinstance(parsing_error, Exception):
            raise parsing_error
        raise MissingParsedOutput(f"{component_name}: 구조화 출력 파싱 실패: {parsing_error}")
    parsed = result.get("parsed")
    if parsed is None:
        raise MissingParsedOutput(f"{component_name}: 구조화 출력이 비어 있습니다.")
    return output_schema.model_validate(parsed)
