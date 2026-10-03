"""에이전트 공통 Base.

LLM 호출 1건(메시지 조립 → 호출 → 결과 확인 → 사용량 기록 → 예외 변환)을 맡는다.
각 에이전트는 ``AgentSpec``으로 설정을 선언하고, 입력을 모델에 보낼 내용으로 바꾸는 일과
결과 후처리만 맡는다. 호출 순서는 파이프라인이 정하며 Base는 관여하지 않는다.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Generic, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .. import prompts
from ..config import build_chat_model
from ..llm_call import track_llm_call

OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentFailure(StrEnum):
    """에이전트 실패 종류. 재시도 판단과 오류 분류의 기준."""

    CALL = "call_failed"  # API 호출 자체 실패 (타임아웃, 레이트리밋, 인증 등)
    PARSE = "parse_failed"  # 응답은 받았지만 출력 스키마로 바꾸지 못함


class AgentError(RuntimeError):
    """에이전트 실패 공통 상위 예외.

    호출부는 SDK의 세부 예외 대신 이 예외(또는 에이전트별 하위 예외)만 잡으면 된다.
    원인 예외는 ``raise ... from``으로 ``__cause__``에 보존한다.

    Attributes:
        agent: 실패한 에이전트 이름.
        failure: 실패 종류. 모델 호출 전 실패면 None.
        partial_result: 실패 전까지 완료한 결과 (예: 검증의 규칙 검사 결과).
    """

    def __init__(
        self,
        message: str,
        *,
        agent: str | None = None,
        failure: AgentFailure | None = None,
        partial_result: Any = None,
    ) -> None:
        super().__init__(message)
        self.agent = agent
        self.failure = failure
        self.partial_result = partial_result


@dataclass(frozen=True)
class AgentSpec:
    """에이전트 하나의 설정.

    Attributes:
        name: 에이전트 이름. 사용량 로그의 기본 이름으로도 쓴다.
        prompt: 공용 프롬프트 로더에 등록된 프롬프트 이름.
        output: 구조화 출력 스키마.
        error: 실패 시 던질 예외 (AgentError 하위 클래스).
        call_failed_message: 호출 실패 메시지. ``{exc}``, ``{exc_type}`` 치환.
        parse_failed_message: 파싱 실패 메시지. ``{error}`` 치환.
        strict: True면 ``method="json_schema", strict=True``로 스키마를 강제.
        requires_model: False면 모델 없이도 생성 가능 (검증의 규칙 전용 실행).
    """

    name: str
    prompt: str
    output: type[BaseModel]
    error: type[AgentError]
    call_failed_message: str
    parse_failed_message: str
    strict: bool = False
    requires_model: bool = True

    def __post_init__(self) -> None:
        if not (isinstance(self.output, type) and issubclass(self.output, BaseModel)):
            raise TypeError("output은 pydantic BaseModel 하위 클래스여야 합니다.")
        if not (isinstance(self.error, type) and issubclass(self.error, AgentError)):
            raise TypeError("error는 AgentError 하위 클래스여야 합니다.")


class StructuredModel(Protocol):
    """``with_structured_output(..., include_raw=True)``가 돌려주는 객체의 최소 인터페이스.

    ``invoke()``는 ``{"raw": AIMessage, "parsed": 출력 | None, "parsing_error": Exception | None}``를 돌려준다.
    """

    def invoke(self, messages: list) -> dict[str, Any]: ...


class ChatModelLike(Protocol):
    """Base가 모델에서 쓰는 메서드만 좁힌 타입. ``BaseChatModel``과 테스트 스텁 모두 만족한다."""

    def with_structured_output(self, schema: type, **kwargs: Any) -> StructuredModel: ...


class BaseAgent(Generic[OutputT]):
    """에이전트 공통 Base. 하위 클래스는 ``spec``을 선언해야 한다."""

    spec: ClassVar[AgentSpec]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not isinstance(getattr(cls, "spec", None), AgentSpec):
            raise TypeError(f"{cls.__name__}에는 AgentSpec 타입의 spec이 필요합니다.")

    def __init__(
        self,
        model: ChatModelLike | None = None,
        *,
        configured_model: str | None = None,
        usage_agent: str | None = None,
    ) -> None:
        """모델을 준비한다.

        Args:
            model: 구조화 출력을 지원하는 모델. None이면 ``requires_model``일 때만
                ``build_chat_model()``로 만든다.
            configured_model: 비용 계산에 쓸 모델 이름. None이면 model의 model_name.
            usage_agent: 사용량 로그 이름. None이면 ``spec.name``.
                평가·운영 구분용 과도기 인자로, 실행 컨텍스트(run_type) 도입 시 제거 예정.
        """
        spec = self.spec
        if model is None and spec.requires_model:
            model = build_chat_model()
        self._configured_model = configured_model or getattr(model, "model_name", None)
        self._usage_agent = usage_agent or spec.name
        self._structured: StructuredModel | None = (
            None if model is None else model.with_structured_output(spec.output, **self._structured_options())
        )
        # 에이전트 모듈 로거로 남겨 모듈별 로그 설정(예: scripts/try_extraction.py)을 유지
        self._logger = logging.getLogger(type(self).__module__)

    @property
    def system_prompt(self) -> str:
        """모델에 보내는 시스템 프롬프트 (공용 로더에서 캐시)."""
        return prompts.load_prompt(self.spec.prompt)

    @property
    def prompt_version(self) -> str:
        """시스템 프롬프트의 지문. 모델에 보내는 원문과 같은 캐시 값으로 계산한다."""
        return prompts.prompt_fingerprint(self.spec.prompt)

    def _structured_options(self) -> dict[str, Any]:
        # 사용량은 원본 응답에서 읽고, 파싱 실패는 예외 대신 parsing_error로 받음
        options: dict[str, Any] = {"include_raw": True}
        if self.spec.strict:
            options.update(method="json_schema", strict=True)
        return options

    def _messages(self, user_content: Any) -> list[SystemMessage | HumanMessage]:
        """시스템 프롬프트와 사용자 입력으로 메시지 목록을 만든다.

        Args:
            user_content: HumanMessage 내용 (문자열 또는 멀티모달 블록 목록).

        Returns:
            list[SystemMessage | HumanMessage]: [시스템 프롬프트, 사용자 입력].
        """
        return [SystemMessage(content=self.system_prompt), HumanMessage(content=user_content)]

    def _invoke(
        self,
        user_content: Any,
        *,
        subject_id: str | None,
        partial_result: Any = None,
    ) -> OutputT:
        """모델을 1번 호출해 구조화 출력을 돌려준다. 호출 1건은 사용량 로그에 한 줄 남는다.

        Args:
            user_content: 모델에 보낼 사용자 입력.
            subject_id: 사용량 로그에 남길 대상 식별자 (예: product_id).
            partial_result: 실패 시 예외에 담아 보존할 부분 결과.

        Returns:
            OutputT: ``spec.output`` 스키마로 파싱한 결과.

        Raises:
            AgentError: ``spec.error`` 타입. 모델이 없거나, 호출이 실패했거나,
                응답을 출력 스키마로 바꾸지 못한 경우.
        """
        spec = self.spec
        if self._structured is None:
            raise spec.error(
                f"{spec.name} 에이전트에 모델이 없어 호출할 수 없습니다.",
                agent=spec.name,
                partial_result=partial_result,
            )

        messages = self._messages(user_content)
        with track_llm_call(
            self._usage_agent,
            configured_model=self._configured_model,
            subject_id=subject_id,
            logger=self._logger,
        ) as call:
            try:
                result = self._structured.invoke(messages)
            except Exception as exc:
                call.fail(type(exc).__name__)
                raise spec.error(
                    spec.call_failed_message.format(exc=exc, exc_type=type(exc).__name__),
                    agent=spec.name,
                    failure=AgentFailure.CALL,
                    partial_result=partial_result,
                ) from exc

            call.use_response(result.get("raw"))
            parsing_error = result.get("parsing_error")
            parsed = result.get("parsed")
            if parsing_error is not None or parsed is None:
                call.fail(type(parsing_error).__name__ if parsing_error else "MissingParsedOutput")
                raise spec.error(
                    spec.parse_failed_message.format(error=parsing_error),
                    agent=spec.name,
                    failure=AgentFailure.PARSE,
                    partial_result=partial_result,
                ) from parsing_error
        return parsed
