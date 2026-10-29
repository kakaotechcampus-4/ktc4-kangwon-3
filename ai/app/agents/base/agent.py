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

from ...clients.llm import build_agent_model, build_tool_model
from ...clients.llm.decision import DecisionClient, DecisionResponseError, check_request, get_decision_client
from ...config import DecisionProfile, agent_decision_profile
from ...observability.agent_sinks import agent_sinks
from ...prompts import PromptName, PromptSnapshot, get_prompt
from ...schemas.clients.decision_request import DecisionQuestion, DecisionRequest
from ...schemas.clients.decision_response import DecisionResponse
from ...usage import CallUsage, estimate_krw, from_completion, from_decision, from_response
from .errors import AgentError, MissingParsedOutput, ModelFailurePhase
from .meta import AgentResult, AgentRunMeta
from .parsing import parse_structured_output
from .protocols import InputT, ModelLike, OutputT, ResultT
from .usage_log import log_token_usage


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
        decision_client: DecisionClient | None = None,
        decision_model: str | None = None,
    ) -> None:
        """에이전트를 만든다.

        출력 스키마는 pydantic 클래스 대신 같은 JSON 스키마 dict로 넘김 (클래스를 넘기면 SDK가 스트림 도중
        파싱하다 예외를 내 실패 호출의 사용량이 기록되지 않음). ``include_raw``로 원본 응답의 사용량·본문을 읽음.

        판단 모델은 AGENT_DECISION_PROFILES에 있는 에이전트만 준비함. 없으면 ``_call_decision``을 못 씀.
        판단 클라이언트는 첫 판단 호출 때 공유 연결로 가져옴 (판단을 안 부르는 실행·테스트는 설정을 안 읽음).

        Args:
            model: 구조화 출력 모델. None이면 프로필로 만들거나(``creates_default_model``) 모델 없이 둠.
            configured_model: 비용 계산용 모델 이름. None이면 model의 model_name.
            usage_agent: 사용량 기록 이름. None이면 component_name.
            decision_client: 판단 클라이언트. None이면 판단 프로필로 가져오거나 판단 모델 없이 둠.
            decision_model: 판단 모델 등록명 (요청·비용 계산용). decision_client를 주면 필수.

        Raises:
            ConfigError: 모델을 만들어야 하는데 설정이 없거나 잘못된 경우.
            ValueError: decision_client만 주고 decision_model을 안 준 경우.
        """
        # 미주입 + 자동 생성 대상이면 프로필로 생성 (검증처럼 creates_default_model=False면 모델 없이 둠)
        if model is None and self.creates_default_model:
            kind, name = self.model_profile or ("agent", self.component_name)
            model = build_tool_model(name) if kind == "tool" else build_agent_model(name)
        self._configured_model = configured_model or getattr(model, "model_name", None)
        self._reasoning_effort = getattr(model, "reasoning_effort", None)
        self._usage_agent = usage_agent or self.component_name
        self._decision_client = decision_client
        self._decision_profile, self._decision_model = self._prepare_decision(decision_client, decision_model)
        self._structured = (
            None
            if model is None
            else model.with_structured_output(
                type_to_response_format_param(self.output_schema)["json_schema"],
                include_raw=True,
                **self.structured_output_options,
            )
        )

    def _prepare_decision(
        self, client: DecisionClient | None, model: str | None,
    ) -> tuple[DecisionProfile | None, str | None]:
        """판단 프로필과 판단 모델 등록명을 정한다. 클라이언트는 만들지 않음 (첫 판단 호출 때 가져옴).

        Args:
            client: 주입한 판단 클라이언트.
            model: 주입한 판단 모델 등록명.

        Returns:
            tuple[DecisionProfile | None, str | None]: 판단 프로필(클라이언트를 주입했으면 None)과 등록명.
            판단 모델을 안 쓰면 둘 다 None.

        Raises:
            ValueError: client만 주고 model을 안 준 경우.
        """
        if client is not None:
            if not model:
                raise ValueError(f"{self.component_name}: decision_client를 주면 decision_model도 줘야 합니다.")
            return None, model
        profile = agent_decision_profile(self.component_name)
        return (profile, profile.model.id) if profile else (None, None)

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
            AgentError: 모델 호출·파싱·후처리 실패. 실제 타입은 ``error_class``.
        """
        return self.run_with_meta(input).result

    def run_with_meta(self, input: InputT) -> AgentResult[ResultT]:
        """입력을 처리해 결과와 실행 정보를 돌려준다.

        흐름: ``_skip`` → ``_build_messages`` → 모델 호출 → ``_finalize``. 사용량은 ``_finalize``까지 끝난 뒤
        한 번 기록 (후처리 실패도 ``failure_phase="finalize"`` 실패로).

        Args:
            input: 에이전트 입력.

        Returns:
            AgentResult[ResultT]: 결과와 실행 정보. 모델 없이 끝났으면 사용량 없는 실행 정보.

        Raises:
            AgentError: 모델 호출·파싱·후처리 실패. 실제 타입은 ``error_class``, 실행 정보는 ``meta``.
        """
        skipped = self._skip(input)
        # 모델 호출 없이 결과가 정해지는 입력 (예: 이미지 0장)
        if skipped is not None:
            return AgentResult(skipped, self._run_meta())
        messages = self._build_messages(input)
        subject_id = self._subject_id(input)
        output, usage, started_at = self._call_model(messages, subject_id=subject_id)
        try:
            result = self._finalize(output, input)
        except Exception as exc:
            # 출력은 스키마에 맞으나 후처리 실패 (예: 입력에 없는 이미지 번호) → 실패로 기록
            self._fail_after_call(exc, usage, subject_id, started_at)
        return AgentResult(result, self._finish_call(usage, subject_id, started_at))

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

        호출 직후 성공으로 기록하므로 결과를 받은 뒤 실패할 수 있는 후처리가 있으면 쓰지 말 것
        (``_invoke_with_meta`` 참고).

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

        호출 직후 성공으로 기록하므로, 결과를 받은 뒤 실패할 수 있는 후처리(검사·병합 등)가 있으면 쓰지 말 것.
        그 경우 ``_call_model``로 받고 후처리가 끝난 뒤 ``_finish_call``(성공)이나 ``_fail_after_call``(실패)로
        기록 (후처리 실패가 성공으로 남지 않게, ``run_with_meta``·검증 에이전트가 이 방식).

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
        output, usage, started_at = self._call_model(messages, subject_id=subject_id, partial_result=partial_result)
        return output, self._finish_call(usage, subject_id, started_at)

    def _call_model(
        self,
        messages: list[Any],
        *,
        subject_id: str,
        partial_result: object | None = None,
    ) -> tuple[OutputT, CallUsage | None, float]:
        """모델을 호출해 구조화 출력을 받는다. 실패는 바로 기록하고, 성공 기록은 후처리 뒤 호출부가 남김.

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 ID (상품 ID).
            partial_result: 실패 시 예외에 담을 부분 결과.

        Returns:
            tuple[OutputT, CallUsage | None, float]: 검증된 출력, 사용량, 호출 시작 시각(perf_counter).
            호출부가 ``_finish_call``(성공)이나 ``_fail_after_call``(후처리 실패)로 한 번 기록해야 함.

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

        log_token_usage(self.component_name, usage, raw_message)
        return output, usage, started_at

    def _call_decision(
        self,
        subject: dict[str, Any],
        questions: list[DecisionQuestion],
        *,
        subject_id: str,
        partial_result: object | None = None,
    ) -> tuple[DecisionResponse, CallUsage, float]:
        """판단 모델에 질문하고 질문 이름별 답을 받는다. 실패는 바로 기록하고, 성공 기록은 후처리 뒤 호출부가 남김.

        호출부는 답으로 결과를 만든 뒤 ``_finish_call(..., called_model=self._decision_model)``(성공)이나
        ``_fail_after_call(..., called_model=self._decision_model)``(후처리 실패)로 한 번 기록해야 함.

        Args:
            subject: 판단 대상 정보 (예: 상품 정보).
            questions: 질문 목록. 이름이 겹치지 않아야 함.
            subject_id: 사용량 기록 대상 ID (상품 ID).
            partial_result: 실패 시 예외에 담을 부분 결과.

        Returns:
            tuple[DecisionResponse, CallUsage, float]: 질문 이름별 답, 사용량, 호출 시작 시각(perf_counter).

        Raises:
            AgentError: 호출 실패(call)·응답 변환 실패(parsing). 실제 타입은 ``error_class``, 원인은 ``__cause__``.
            RuntimeError: 판단 모델 없이 호출한 경우.
            DecisionRequestError: 질문 이름·후보 값이 겹치는 경우. 코드 오류라 실패로 기록하지 않음.
            ConfigError: 판단 클라이언트를 처음 가져오는데 설정이 없거나 잘못된 경우.
        """
        client = self._decision_client_or_none()
        if client is None:
            raise RuntimeError(f"{self.component_name}: 판단 모델 없이 _call_decision을 호출했습니다.")

        request = DecisionRequest(model=self._decision_model, subject=subject, questions=questions)
        check_request(request)
        started_at = perf_counter()
        try:
            response = client.decide(request)
        except DecisionResponseError as exc:
            # 응답은 받았으나 모양이 다르거나 답이 빠짐 → 읽은 토큰까지 기록
            usage = from_decision(exc.usage) if exc.usage else None
            self._fail(ModelFailurePhase.PARSING, exc, usage, subject_id, started_at, partial_result,
                       called_model=self._decision_model)
        except Exception as exc:
            # 응답 자체를 못 받음 (네트워크·타임아웃·인증·4xx·5xx)
            self._fail(ModelFailurePhase.CALL, exc, None, subject_id, started_at, partial_result,
                       called_model=self._decision_model)
        return response, from_decision(response.usage), started_at

    def _decision_client_or_none(self) -> DecisionClient | None:
        """판단 클라이언트. 주입하지 않았으면 판단 프로필의 공유 클라이언트를 처음 쓸 때 가져옴.

        Returns:
            DecisionClient | None: 판단 클라이언트. 판단 모델을 안 쓰는 에이전트면 None.

        Raises:
            ConfigError: 설정이 없거나 잘못된 경우.
        """
        if self._decision_client is None and self._decision_profile is not None:
            self._decision_client = get_decision_client(self._decision_profile)
        return self._decision_client

    def _decision_failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """판단 호출 실패 문구를 만든다. 채팅 출력 스키마와 무관해 작업 이름으로만 씀.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        if phase is ModelFailurePhase.CALL:
            return f"{self.task_name} 판단 모델 호출에 실패했습니다: {cause}"
        return f"{self.task_name} 판단 모델 응답을 해석하지 못했습니다: {cause}"

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
        failure_phase: ModelFailurePhase | None = None,
        called_model: str | None = None,
    ) -> AgentRunMeta:
        """이 에이전트의 모델·프롬프트 정보로 실행 정보를 만든다.

        Args:
            usage: 사용량. 모르거나 호출이 없었으면 None.
            elapsed_ms: 걸린 시간(ms).
            error_type: 실패 원인 예외 이름. 성공이면 None.
            failure_phase: 실패 단계. 성공이면 None.
            called_model: 채팅 모델 말고 다른 모델(판단 모델 등)을 불렀으면 그 등록명. 추론 강도·프롬프트는
                없음으로 남김. None이면 채팅 모델과 그 추론 강도·시스템 프롬프트.

        Returns:
            AgentRunMeta: 실행 정보.
        """
        # 판단 모델처럼 다른 모델 호출은 시스템 프롬프트를 안 써서 프롬프트 지문을 남기지 않음
        prompt = None if called_model else self.prompt
        model = called_model or self._configured_model
        return AgentRunMeta(
            component=self.component_name,
            usage_name=self._usage_agent,
            model=model,
            reasoning_effort=None if called_model else self._reasoning_effort,
            prompt_name=prompt.name.value if prompt else None,
            prompt_sha256=prompt.sha256 if prompt else None,
            usage=usage,
            cost_krw=estimate_krw(usage, model) if usage else None,
            elapsed_ms=elapsed_ms,
            error_type=error_type,
            failure_phase=failure_phase.value if failure_phase else None,
        )

    def _finish_call(
        self,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        *,
        error_type: str | None = None,
        failure_phase: ModelFailurePhase | None = None,
        called_model: str | None = None,
    ) -> AgentRunMeta:
        """호출 1건을 마무리한다. 걸린 시간을 한 번 재서 실행 정보를 만들고 sink 등록표에 넘김.

        Args:
            usage: 사용량. 호출 실패로 모르면 None.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            error_type: 실패 원인 예외 이름. 성공이면 None.
            failure_phase: 실패 단계. 성공이면 None.
            called_model: 채팅 모델 말고 다른 모델을 불렀으면 그 등록명. None이면 채팅 모델.

        Returns:
            AgentRunMeta: 실행 정보.
        """
        elapsed_ms = round((perf_counter() - started_at) * 1000)
        meta = self._run_meta(
            usage=usage, elapsed_ms=elapsed_ms, error_type=error_type, failure_phase=failure_phase,
            called_model=called_model,
        )
        # 사용량 로그(usage.jsonl)도 기본 등록된 sink 중 하나 (usage_log.record_call)
        agent_sinks.publish(meta, subject_id)
        return meta

    def _fail(
        self,
        phase: ModelFailurePhase,
        cause: Exception,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        partial_result: object | None,
        *,
        called_model: str | None = None,
    ) -> NoReturn:
        """실패 호출을 기록하고 원인 예외를 ``error_class``로 감싸 던진다.

        Args:
            phase: 실패 단계. 문구 선택에 씀.
            cause: 원인 예외. ``__cause__``로 연결.
            usage: 사용량. 호출 실패로 모르면 None.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            partial_result: 예외에 담을 부분 결과.
            called_model: 채팅 모델 말고 다른 모델을 불렀으면 그 등록명. None이면 채팅 모델.

        Raises:
            AgentError: 항상. 실제 타입은 ``error_class``, 실행 정보는 ``meta``.
        """
        meta = self._finish_call(
            usage, subject_id, started_at, error_type=type(cause).__name__, failure_phase=phase,
            called_model=called_model,
        )
        raise self.error_class(
            self._decision_failure_message(phase, cause) if called_model else self._failure_message(phase, cause),
            partial_result=partial_result,
            meta=meta,
        ) from cause

    def _fail_after_call(
        self,
        exc: Exception,
        usage: CallUsage | None,
        subject_id: str,
        started_at: float,
        *,
        partial_result: object | None = None,
        called_model: str | None = None,
    ) -> NoReturn:
        """후처리 실패를 ``failure_phase="finalize"`` 실패로 기록하고 받은 예외를 그대로 던진다.

        에이전트 예외면 실행 정보·부분 결과를 채움. 그 밖의 예외(코드 버그 등)는 감싸지 않음.

        Args:
            exc: 후처리에서 난 예외.
            usage: 이미 쓴 토큰 사용량.
            subject_id: 기록 대상 ID (상품 ID).
            started_at: 호출 시작 시각 (perf_counter).
            partial_result: 예외에 담을 부분 결과. None이면 기존 값 유지.
            called_model: 채팅 모델 말고 다른 모델을 불렀으면 그 등록명. None이면 채팅 모델.

        Raises:
            Exception: 받은 예외 그대로.
        """
        # 에이전트 예외가 원인을 감싼 경우 → 원인 이름으로 기록 (모니터링에서 실패 이유를 구분)
        cause = exc.__cause__ if isinstance(exc, AgentError) and exc.__cause__ is not None else exc
        meta = self._finish_call(
            usage, subject_id, started_at, error_type=type(cause).__name__, failure_phase=ModelFailurePhase.FINALIZE,
            called_model=called_model,
        )
        if isinstance(exc, AgentError):
            exc.meta = exc.meta or meta
            # 부분 결과를 넘긴 경우만 덮어씀
            if partial_result is not None:
                exc.partial_result = partial_result
        raise exc
