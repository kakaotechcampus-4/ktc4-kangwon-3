"""에이전트 공통 베이스. 모델 준비·구조화 출력 호출·예외 변환 (#171 §4 M1)."""

from time import perf_counter
from typing import Any, ClassVar, Generic, Literal, NoReturn

from langchain_core.messages import HumanMessage, SystemMessage
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel

from ...config import build_agent_model, build_tool_model
from ...prompts import PromptName, PromptSnapshot, get_prompt
from ...usage import CallUsage, from_completion, from_response
from .errors import AgentError, ModelFailurePhase
from .parsing import OutputT, parse_structured_output
from .protocols import ModelLike
from .usage_log import log_token_usage, record_call


class BaseAgent(Generic[OutputT]):
    """구조화 출력 모델 호출을 맡는 에이전트 부모. 하위 클래스는 필수 변수 4개와 ``_failure_message``를 정의.

    Attributes:
        component_name: 에이전트 이름. 프로필·사용량 기록·오류 문구에 씀 (필수)
        prompt_name: 시스템 프롬프트 (필수)
        output_schema: 구조화 출력 스키마 (필수)
        error_class: 실패 시 던질 예외. AgentError 하위 (필수)
        structured_output_options: with_structured_output 추가 옵션 (예: strict)
        creates_default_model: 모델 미주입 시 프로필로 만들지. 검증 에이전트는 규칙 전용 실행 때문에 False
        model_profile: (표 종류, 이름). None이면 ("agent", component_name). Tool 안 에이전트는 ("tool", ToolName 값)
    """

    component_name: ClassVar[str]
    prompt_name: ClassVar[PromptName]
    output_schema: ClassVar[type[BaseModel]]
    error_class: ClassVar[type[AgentError]]
    structured_output_options: ClassVar[dict[str, Any]] = {}
    creates_default_model: ClassVar[bool] = True
    model_profile: ClassVar[tuple[Literal["agent", "tool"], str] | None] = None

    def __init__(
        self,
        model: ModelLike | None = None,
        *,
        configured_model: str | None = None,
        usage_agent: str | None = None,
    ) -> None:
        """에이전트를 만든다.

        출력 스키마는 pydantic 클래스 대신 같은 JSON 스키마 dict로 넘김 (클래스를 넘기면 SDK가 스트림 도중
        파싱하다 예외를 내 실패 호출의 사용량이 기록되지 않음). ``include_raw``로 원본 응답의 사용량·본문을 읽음.

        Args:
            model: 구조화 출력 모델. None이면 프로필로 만들거나(``creates_default_model``) 모델 없이 둠.
            configured_model: 비용 계산용 모델 이름. None이면 model의 model_name.
            usage_agent: 사용량 기록 이름. None이면 component_name.

        Raises:
            ConfigError: 모델을 만들어야 하는데 설정이 없거나 잘못된 경우.
        """
        # 미주입 + 자동 생성 대상이면 프로필로 생성 (검증처럼 creates_default_model=False면 모델 없이 둠)
        if model is None and self.creates_default_model:
            kind, name = self.model_profile or ("agent", self.component_name)
            model = build_tool_model(name) if kind == "tool" else build_agent_model(name)
        self._configured_model = configured_model or getattr(model, "model_name", None)
        self._reasoning_effort = getattr(model, "reasoning_effort", None)
        self._usage_agent = usage_agent or self.component_name
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
        """시스템 프롬프트 스냅샷 (원문·경로·지문)."""
        return get_prompt(self.prompt_name)

    def _messages(self, human_content: str | list[dict[str, Any]]) -> list[SystemMessage | HumanMessage]:
        """[시스템 프롬프트, 사용자 입력] 메시지를 만든다.

        Args:
            human_content: 사용자 입력. 텍스트 또는 텍스트·이미지 블록 목록.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.
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
            partial_result: 실패 시 예외에 담을 부분 결과.

        Returns:
            OutputT: 검증된 출력.

        Raises:
            AgentError: 호출·파싱 실패. 실제 타입은 ``error_class``, 원인은 ``__cause__``.
            RuntimeError: 모델 없이 호출한 경우.
        """
        # 모델 미주입 상태 (creates_default_model=False 에이전트를 모델 없이 만든 경우)
        if self._structured is None:
            raise RuntimeError(f"{self.component_name}: 모델 없이 _invoke를 호출했습니다.")

        started_at = perf_counter()
        try:
            result = self._structured.invoke(messages)
        except (LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
            # 응답은 받았으나 길이 초과·콘텐츠 필터로 출력이 잘림 → 예외에 담긴 사용량 기록
            usage = from_completion(exc.completion)
            self._record_usage(usage, subject_id, started_at, error_type=type(exc).__name__)
            self._raise_model_error(ModelFailurePhase.PARSING, exc, partial_result=partial_result)
        except Exception as exc:
            # 응답 자체를 못 받음 (네트워크·타임아웃·인증·서버 오류) → 사용량 없이 실패만 기록
            self._record_usage(None, subject_id, started_at, error_type=type(exc).__name__)
            self._raise_model_error(ModelFailurePhase.CALL, exc, partial_result=partial_result)

        raw_message = result.get("raw")
        usage = from_response(raw_message)
        try:
            output = parse_structured_output(result, self.output_schema, self.component_name)
        except Exception as cause:
            # 응답은 받았으나 거절·JSON 오류·스키마 위반·빈 출력 → 쓴 토큰까지 기록
            self._record_usage(usage, subject_id, started_at, error_type=type(cause).__name__)
            self._raise_model_error(ModelFailurePhase.PARSING, cause, partial_result=partial_result)

        self._record_usage(usage, subject_id, started_at)
        log_token_usage(self.component_name, usage, raw_message)
        return output

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 예외 문구를 만든다. 하위 클래스가 정의.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.

        Raises:
            NotImplementedError: 하위 클래스가 정의하지 않은 경우.
        """
        raise NotImplementedError

    def _raise_model_error(
        self,
        phase: ModelFailurePhase,
        cause: Exception,
        *,
        partial_result: object | None = None,
    ) -> NoReturn:
        """원인 예외를 ``error_class``로 감싸 던진다.

        Args:
            phase: 실패 단계. 문구 선택에 씀.
            cause: 원인 예외. ``__cause__``로 연결.
            partial_result: 예외에 담을 부분 결과.

        Raises:
            AgentError: 항상. 실제 타입은 ``error_class``.
        """
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
        """호출 1건을 이 에이전트 이름·모델로 사용량 로그에 남긴다.

        Args:
            usage: 사용량. 호출 실패로 모르면 None.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            error_type: 실패 원인 예외 이름. 성공이면 None.
        """
        record_call(
            self._usage_agent,
            usage,
            configured_model=self._configured_model,
            reasoning_effort=self._reasoning_effort,
            subject_id=subject_id,
            started_at=started_at,
            error_type=error_type,
        )
