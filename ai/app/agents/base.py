"""에이전트 공통 모델 호출·사용량 기록·예외 변환 (#171 §4 M1).

각 에이전트는 프롬프트·출력 스키마·예외·실패 문구만 정하고, 모델 호출 순서는 Base가 맡음.
"""

import logging
from enum import StrEnum
from time import perf_counter
from typing import Any, ClassVar, Generic, NoReturn, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel

from ..config import build_chat_model
from ..prompts import PromptName, PromptSnapshot, get_prompt
from ..usage import CallUsage, from_response, record

logger = logging.getLogger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredModel(Protocol):
    """``with_structured_output(..., include_raw=True)``가 돌려주는 객체의 최소 인터페이스.

    invoke()는 ``{"raw": AIMessage, "parsed": 출력 | None, "parsing_error": Exception | None}``을 돌려줌.
    """

    def invoke(self, messages: list[Any]) -> dict[str, Any]: ...


class ModelLike(Protocol):
    """에이전트가 받는 모델의 최소 인터페이스.

    ``BaseChatModel``과 테스트 스텁 모두 이 구조를 만족함.
    """

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any) -> StructuredModel: ...


class AgentError(RuntimeError):
    """에이전트 모델 호출·파싱 실패의 공통 부모.

    Attributes:
        partial_result: 실패 전까지 만든 부분 결과. 없으면 None.
    """

    def __init__(self, message: str, *, partial_result: object | None = None) -> None:
        super().__init__(message)
        self.partial_result = partial_result


class MissingParsedOutput(RuntimeError):
    """파싱 오류 없이 구조화 출력이 비어 온 경우의 원인 예외."""


def _usage_from_completion(completion: Any) -> CallUsage | None:
    """SDK 종료 사유 예외에 담긴 ChatCompletion에서 사용량을 꺼낸다. 없으면 None."""
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    return CallUsage(
        reported_model=getattr(completion, "model", None) or "",
        input_tokens=usage.prompt_tokens or 0,
        cached_tokens=getattr(details, "cached_tokens", 0) or 0,
        output_tokens=usage.completion_tokens or 0,
    )


class ModelFailurePhase(StrEnum):
    CALL = "call"
    PARSING = "parsing"


class BaseAgent(Generic[OutputT]):
    """구조화 출력 모델 호출을 공통으로 처리하는 에이전트 부모.

    하위 클래스는 필수 클래스 변수 4개와 ``_failure_message``를 정의함.
    """

    component_name: ClassVar[str]
    prompt_name: ClassVar[PromptName]
    output_schema: ClassVar[type[BaseModel]]
    error_class: ClassVar[type[AgentError]]
    # 문서 §4.2 확장. strict 등 에이전트별 기존 구조화 출력 설정 유지용
    structured_output_options: ClassVar[dict[str, Any]] = {}
    # 문서 §4.2 확장. 모델 미주입 시 build_chat_model()로 생성할지. 검증은 규칙 전용 실행 때문에 False
    creates_default_model: ClassVar[bool] = True

    def __init__(
        self,
        model: ModelLike | None = None,
        *,
        configured_model: str | None = None,
        usage_agent: str | None = None,
    ) -> None:
        """에이전트를 만든다.

        Args:
            model: 구조화 출력을 지원하는 모델. None이면 ``creates_default_model``에 따라
                ``build_chat_model()``로 만들거나, 모델 없이 둠 (검증 규칙 전용 실행).
            configured_model: 비용 계산에 쓸 모델 이름. None이면 model의 model_name.
            usage_agent: 사용량 기록 이름. None이면 component_name.

        Raises:
            ConfigError: 모델을 만들어야 하는데 설정이 없거나 잘못된 경우.
        """
        # 모델 생성은 config.build_chat_model() 한 곳에서. base_url·허용 모델·타임아웃 설정이 흩어지지 않게 함
        if model is None and self.creates_default_model:
            model = build_chat_model()
        self._configured_model = configured_model or getattr(model, "model_name", None)
        self._usage_agent = usage_agent or self.component_name
        # include_raw: 원본 응답에서 토큰 사용량을 읽고, JSON 오류를 parsing_error로 받음
        # 스키마는 Pydantic 클래스가 아닌 dict로 넘김. 클래스를 넘기면 SDK가 스트림 도중 파싱하다
        # 사용량 조각을 받기 전에 예외를 내서 파싱 실패·길이 초과 시 토큰 비용이 기록되지 않음.
        # dict는 SDK가 클래스를 변환할 때와 같은 함수로 만들어 요청 본문은 그대로.
        # LangChain은 {"name", "schema", "strict"} 형태만 받아 json_schema 안쪽을 넘김
        self._structured = (
            None
            if model is None
            else model.with_structured_output(
                type_to_response_format_param(self.output_schema)["json_schema"],
                include_raw=True,
                **self.structured_output_options,
            )
        )

    @property
    def prompt(self) -> PromptSnapshot:
        """이 에이전트의 프롬프트 스냅샷."""
        return get_prompt(self.prompt_name)

    def _messages(self, human_content: str | list[dict[str, Any]]) -> list[SystemMessage | HumanMessage]:
        """시스템 프롬프트와 사용자 입력으로 모델 메시지를 만든다.

        Args:
            human_content: 사용자 메시지 내용. 텍스트 또는 텍스트·이미지 블록 목록.

        Returns:
            list[SystemMessage | HumanMessage]: [시스템 프롬프트, 사용자 입력].
        """
        return [SystemMessage(content=self.prompt.text), HumanMessage(content=human_content)]

    def _invoke(
        self,
        messages: list[Any],
        *,
        subject_id: str,
        partial_result: object | None = None,
    ) -> OutputT:
        """모델을 호출해 구조화 출력을 돌려준다. 성공·실패 모두 사용량을 한 번 기록.

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 ID (상품 ID).
            partial_result: 실패 시 예외에 보존할 부분 결과.

        Returns:
            OutputT: 파싱된 출력.

        Raises:
            AgentError: 호출 또는 파싱 실패 시 ``error_class`` 예외. 원인은 ``__cause__``에 보존.
            RuntimeError: 모델 없이 호출한 경우. 호출 전 하위 클래스에서 막아야 함.
        """
        if self._structured is None:
            raise RuntimeError(f"{self.component_name}: 모델 없이 _invoke를 호출했습니다.")

        started_at = perf_counter()
        try:
            result = self._structured.invoke(messages)
        except (LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
            # 응답은 다 받았지만 길이 초과·필터로 출력이 잘린 경우. SDK가 예외에 사용량을 담아 줌
            usage = _usage_from_completion(exc.completion)
            self._record_usage(usage, subject_id, started_at, error_type=type(exc).__name__)
            self._raise_model_error(ModelFailurePhase.PARSING, exc, partial_result=partial_result)
        except Exception as exc:
            # 호출 실패는 사용량을 알 수 없음. 시도 횟수 집계용으로 실패만 기록
            self._record_usage(None, subject_id, started_at, error_type=type(exc).__name__)
            self._raise_model_error(ModelFailurePhase.CALL, exc, partial_result=partial_result)

        raw_message = result.get("raw")
        usage = from_response(raw_message)
        try:
            output = self._parse_output(result)
        except Exception as cause:
            # 파싱에 실패해도 토큰은 이미 사용됨
            self._record_usage(usage, subject_id, started_at, error_type=type(cause).__name__)
            self._raise_model_error(ModelFailurePhase.PARSING, cause, partial_result=partial_result)

        self._record_usage(usage, subject_id, started_at)
        self._log_token_usage(usage, raw_message)
        return output

    def _parse_output(self, result: dict[str, Any]) -> OutputT:
        """구조화 출력 결과를 출력 스키마로 검증한다. 응답을 다 받은 뒤 실행돼 사용량이 남아 있음.

        Args:
            result: ``{"raw", "parsed", "parsing_error"}``.

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
            return self.output_schema.model_validate_json(content)

        # 본문이 없는 응답(빈 응답) 또는 parsed를 바로 주는 테스트 스텁
        parsing_error = result.get("parsing_error")
        if parsing_error is not None:
            if isinstance(parsing_error, Exception):
                raise parsing_error
            raise MissingParsedOutput(f"{self.component_name}: 구조화 출력 파싱 실패: {parsing_error}")
        parsed = result.get("parsed")
        if parsed is None:
            raise MissingParsedOutput(f"{self.component_name}: 구조화 출력이 비어 있습니다.")
        return self.output_schema.model_validate(parsed)

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """호출·파싱 실패 시 예외 문구. 각 에이전트가 기존 문구를 돌려줌.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        raise NotImplementedError

    def _raise_model_error(
        self,
        phase: ModelFailurePhase,
        cause: Exception,
        *,
        partial_result: object | None = None,
    ) -> NoReturn:
        """에이전트별 예외로 감싸 던진다. 원인 예외는 cause로 연결."""
        raise self.error_class(
            self._failure_message(phase, cause),
            partial_result=partial_result,
        ) from cause

    def _record_usage(
        self,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        *,
        error_type: str | None = None,
    ) -> None:
        """호출 1건을 공용 사용량 로그에 남긴다. 기록 실패는 호출 결과에 영향 없음."""
        record(
            self._usage_agent,
            usage,
            configured_model=self._configured_model,
            subject_id=subject_id,
            ok=error_type is None,
            elapsed_ms=round((perf_counter() - started_at) * 1000),
            error_type=error_type,
        )

    def _log_token_usage(self, usage: CallUsage | None, raw_message: Any) -> None:
        """수집한 사용량을 콘솔 로그로 출력한다. 출력 실패는 판정에 영향 없음.

        cache_read가 계속 0이면 프롬프트 캐시가 안 먹는 것. 고정 prefix가 호출마다 바뀌는지 확인.
        """
        if usage is None:
            return
        try:
            logger.info(
                "%s 토큰 사용량 input=%s (cache_read=%s) output=%s total=%s",
                self.component_name,
                usage.input_tokens,
                usage.cached_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
            # 게이트웨이 원본 필드명이 OpenAI와 다를 수 있어 디버그로 남김
            response_metadata = getattr(raw_message, "response_metadata", None) or {}
            if response_metadata.get("token_usage"):
                logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
        except Exception:
            pass
