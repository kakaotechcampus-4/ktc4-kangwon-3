"""에이전트 공통 베이스. 공통 실행 인터페이스·모델 준비·구조화 출력 호출·예외 변환 (#171 §4 M1).

공개 입구는 ``run``·``run_with_meta`` 둘뿐이고, 하위 클래스는 입력 → 메시지(``_build_messages``)와
사용량 기록 대상(``_subject_id``)만 구현함. 필요할 때만 ``_finalize``·``_skip``을 다시 정의.
클라이언트의 fetch_parsed/_send/_parse와 같은 구조.
"""

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, ClassVar, Generic, Literal, NoReturn

from langchain_core.messages import HumanMessage, SystemMessage
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel

from ...config import build_agent_model, build_tool_model
from ...prompts import PromptName, PromptSnapshot, get_prompt
from ...usage import CallUsage, estimate_krw, from_completion, from_response
from .errors import AgentError, MissingParsedOutput, ModelFailurePhase
from .meta import AgentResult, AgentRunMeta
from .parsing import parse_structured_output
from .protocols import InputT, ModelLike, OutputT, ResultT
from .usage_log import log_token_usage, record_call


class BaseAgent(ABC, Generic[InputT, OutputT, ResultT]):
    """입력 하나로 구조화 출력 모델을 한 번 호출해 결과를 내는 에이전트 부모.

    하위 클래스는 필수 변수와 ``_build_messages``·``_subject_id``를 정의.

    Attributes:
        component_name: 에이전트 이름. 프로필·사용량 기록·오류 문구에 씀 (필수)
        prompt_name: 시스템 프롬프트 (필수)
        output_schema: 구조화 출력 스키마 (필수)
        error_class: 실패 시 던질 예외. AgentError 하위 (필수)
        task_name: 호출 실패 문구에 쓸 작업 이름 (예: "상품 정보 추출"). ``_failure_message``를 다시 정의하면 생략
        output_label: 파싱 실패 문구에 쓸 출력 이름. None이면 output_schema 클래스 이름
        structured_output_options: with_structured_output 추가 옵션 (예: strict)
        creates_default_model: 모델 미주입 시 프로필로 만들지. 검증 에이전트는 규칙 전용 실행 때문에 False
        model_profile: (표 종류, 이름). None이면 ("agent", component_name). Tool 안 에이전트는 ("tool", ToolName 값)
    """

    component_name: ClassVar[str]
    prompt_name: ClassVar[PromptName]
    output_schema: ClassVar[type[BaseModel]]
    error_class: ClassVar[type[AgentError]]
    task_name: ClassVar[str]
    output_label: ClassVar[str | None] = None
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

    def run(self, input: InputT) -> ResultT:
        """입력을 처리해 결과를 돌려준다.

        Args:
            input: 에이전트 입력.

        Returns:
            ResultT: 에이전트 결과.

        Raises:
            AgentError: 모델 호출·파싱 실패. 실제 타입은 ``error_class``.
        """
        return self.run_with_meta(input).result

    def run_with_meta(self, input: InputT) -> AgentResult[ResultT]:
        """입력을 처리해 결과와 실행 정보를 돌려준다.

        흐름: ``_skip`` → ``_build_messages`` → 모델 호출 → ``_finalize``.

        Args:
            input: 에이전트 입력.

        Returns:
            AgentResult[ResultT]: 결과와 실행 정보. 모델 없이 끝났으면 사용량 없는 실행 정보.

        Raises:
            AgentError: 모델 호출·파싱 실패. 실제 타입은 ``error_class``, 실행 정보는 ``meta``.
        """
        skipped = self._skip(input)
        # 모델 호출 없이 결과가 정해지는 입력 (예: 이미지 0장)
        if skipped is not None:
            return AgentResult(skipped, self._run_meta())
        output, meta = self._invoke_with_meta(self._build_messages(input), subject_id=self._subject_id(input))
        return AgentResult(self._finalize(output, input), meta)

    @abstractmethod
    def _build_messages(self, input: InputT) -> list[Any]:
        """입력을 모델 메시지로 만든다.

        Args:
            input: 에이전트 입력.

        Returns:
            list[Any]: 모델에 보낼 메시지.
        """

    @abstractmethod
    def _subject_id(self, input: InputT) -> str:
        """사용량 기록 대상 ID를 고른다.

        Args:
            input: 에이전트 입력.

        Returns:
            str: 기록 대상 ID (보통 상품 ID).
        """

    def _finalize(self, output: OutputT, input: InputT) -> ResultT:
        """모델 출력을 최종 결과로 바꾼다. 기본은 출력 그대로.

        Args:
            output: 검증된 모델 출력.
            input: 에이전트 입력.

        Returns:
            ResultT: 최종 결과.
        """
        return output  # type: ignore[return-value]

    def _skip(self, input: InputT) -> ResultT | None:
        """모델 호출 없이 정해지는 결과를 돌려준다. 기본은 None(항상 호출).

        Args:
            input: 에이전트 입력.

        Returns:
            ResultT | None: 호출 없이 낼 결과. 호출해야 하면 None.
        """
        return None

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
        """모델을 호출해 구조화 출력만 돌려준다. 실행 정보가 필요하면 ``_invoke_with_meta``.

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 ID (상품 ID).
            partial_result: 실패 시 예외에 담을 부분 결과.

        Returns:
            OutputT: 검증된 출력.

        Raises:
            AgentError: 호출·파싱 실패. 실제 타입은 ``error_class``, 원인은 ``__cause__``, 실행 정보는 ``meta``.
            RuntimeError: 모델 없이 호출한 경우.
        """
        return self._invoke_with_meta(messages, subject_id=subject_id, partial_result=partial_result)[0]

    def _invoke_with_meta(
        self,
        messages: list[Any],
        *,
        subject_id: str,
        partial_result: object | None = None,
    ) -> tuple[OutputT, AgentRunMeta]:
        """모델을 호출해 구조화 출력과 실행 정보를 돌려준다. 성공·실패 모두 사용량을 한 번 기록.

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 ID (상품 ID).
            partial_result: 실패 시 예외에 담을 부분 결과.

        Returns:
            tuple[OutputT, AgentRunMeta]: 검증된 출력과 실행 정보.

        Raises:
            AgentError: 호출·파싱 실패. 실제 타입은 ``error_class``, 원인은 ``__cause__``, 실행 정보는 ``meta``.
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
            self._fail(ModelFailurePhase.PARSING, exc, from_completion(exc.completion), subject_id, started_at,
                       partial_result)
        except Exception as exc:
            # 응답 자체를 못 받음 (네트워크·타임아웃·인증·서버 오류) → 사용량 없이 실패만 기록
            self._fail(ModelFailurePhase.CALL, exc, None, subject_id, started_at, partial_result)

        raw_message = result.get("raw")
        usage = from_response(raw_message)
        try:
            output = parse_structured_output(result, self.output_schema, self.component_name)
        except Exception as cause:
            # 응답은 받았으나 거절·JSON 오류·스키마 위반·빈 출력 → 쓴 토큰까지 기록
            self._fail(ModelFailurePhase.PARSING, cause, usage, subject_id, started_at, partial_result)

        meta = self._finish_call(usage, subject_id, started_at)
        log_token_usage(self.component_name, usage, raw_message)
        return output, meta

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 문구를 만든다. 호출 실패는 작업 이름, 파싱 실패는 출력 이름으로.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        # 응답을 못 받은 실패
        if phase is ModelFailurePhase.CALL:
            return f"{self.task_name}에 실패했습니다: {cause}"
        # 빈 출력이면 원인 자리에 None (기존 문구 유지)
        detail = None if isinstance(cause, MissingParsedOutput) else cause
        label = self.output_label or self.output_schema.__name__
        return f"모델 응답이 {label} 스키마와 맞지 않습니다: {detail}"

    def _run_meta(
        self,
        *,
        usage: CallUsage | None = None,
        elapsed_ms: int = 0,
        error_type: str | None = None,
    ) -> AgentRunMeta:
        """이 에이전트의 모델·프롬프트 정보로 실행 정보를 만든다.

        Args:
            usage: 사용량. 모르거나 호출이 없었으면 None.
            elapsed_ms: 걸린 시간(ms).
            error_type: 실패 원인 예외 이름. 성공이면 None.

        Returns:
            AgentRunMeta: 실행 정보.
        """
        prompt = self.prompt
        return AgentRunMeta(
            component=self.component_name,
            model=self._configured_model,
            reasoning_effort=self._reasoning_effort,
            prompt_name=prompt.name.value,
            prompt_sha256=prompt.sha256,
            usage=usage,
            cost_krw=estimate_krw(usage, self._configured_model) if usage else None,
            elapsed_ms=elapsed_ms,
            error_type=error_type,
        )

    def _finish_call(
        self,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        *,
        error_type: str | None = None,
    ) -> AgentRunMeta:
        """호출 1건을 마무리한다. 걸린 시간을 한 번 재서 사용량 로그와 실행 정보에 같이 씀.

        Args:
            usage: 사용량. 호출 실패로 모르면 None.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            error_type: 실패 원인 예외 이름. 성공이면 None.

        Returns:
            AgentRunMeta: 실행 정보.
        """
        elapsed_ms = round((perf_counter() - started_at) * 1000)
        record_call(
            self._usage_agent,
            usage,
            configured_model=self._configured_model,
            reasoning_effort=self._reasoning_effort,
            subject_id=subject_id,
            elapsed_ms=elapsed_ms,
            error_type=error_type,
        )
        return self._run_meta(usage=usage, elapsed_ms=elapsed_ms, error_type=error_type)

    def _fail(
        self,
        phase: ModelFailurePhase,
        cause: Exception,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        partial_result: object | None,
    ) -> NoReturn:
        """실패 호출을 기록하고 원인 예외를 ``error_class``로 감싸 던진다.

        Args:
            phase: 실패 단계. 문구 선택에 씀.
            cause: 원인 예외. ``__cause__``로 연결.
            usage: 사용량. 호출 실패로 모르면 None.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            partial_result: 예외에 담을 부분 결과.

        Raises:
            AgentError: 항상. 실제 타입은 ``error_class``, 실행 정보는 ``meta``.
        """
        meta = self._finish_call(usage, subject_id, started_at, error_type=type(cause).__name__)
        raise self.error_class(
            self._failure_message(phase, cause),
            partial_result=partial_result,
            meta=meta,
        ) from cause
