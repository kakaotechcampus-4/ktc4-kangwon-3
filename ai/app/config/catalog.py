"""채팅·판단 모델 카탈로그. 게이트웨이에 등록된 모델과 단가 (#279).

엘리스 ML API 게이트웨이는 세 회사 모델을 같은 OpenAI 호환 엔드포인트로 받음 (2026-10-14 실호출 확인).
호출은 모두 ChatOpenAI 하나로 하고, 회사마다 다른 호출 옵션 규칙만 하위 클래스에 둠.

새 모델은 회사 클래스 상수 하나 + CHAT_MODELS에 넣기.
    - 구조화 출력(json_schema)·temperature·추론 강도를 한 번씩 호출해 보고 reasoning_efforts를 채움
    - 단가는 추론 강도와 무관하게 모델당 하나 (세 회사 모두 추론 토큰이 출력 토큰에 포함되어 보고됨)

판단 모델(/decisions)은 DecisionModel 상수 하나 + DECISION_MODELS에 넣기.
    - 요청·응답 형식이 회사마다 달라 vendor로 클라이언트를 고름 (clients.llm.decision)
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Price:
    """1M 토큰당 KRW. 캐시 입력은 입력 토큰 중 캐시 적중분.

    Attributes:
        input: 입력 단가.
        cached_input: 캐시 입력 단가.
        output: 출력 단가.
    """

    input: float
    cached_input: float
    output: float


@dataclass(frozen=True)
class ChatModel:
    """게이트웨이 카탈로그의 채팅 모델 1개. 직접 쓰지 않고 회사 클래스로 만듦.

    Attributes:
        name: 회사 접두어 없는 모델 이름 (예: "gpt-4.1-mini").
        price: 1M 토큰당 KRW. 모르면 None (비용 계산 안 함).
        price_source: 단가 출처·확인일.
        reasoning_efforts: 받는 추론 강도. 비면 추론 강도를 보내지 않음.
        vendor: 카탈로그 등록명 접두어 (회사 클래스가 정함).
    """

    name: str
    price: Price | None
    price_source: str = ""
    reasoning_efforts: tuple[str, ...] = ()
    vendor: ClassVar[str] = ""

    def __post_init__(self) -> None:
        if not self.vendor:
            raise TypeError("ChatModel은 회사 클래스(OpenAIModel·GeminiModel·ClaudeModel)로 만들어야 합니다.")

    @property
    def id(self) -> str:
        """카탈로그 등록명 (예: "openai/gpt-4.1-mini"). 게이트웨이는 접두어 없는 이름을 거부함."""
        return f"{self.vendor}/{self.name}"

    def option_errors(self, temperature: float | None, reasoning_effort: str | None) -> list[str]:
        """이 모델에 줄 수 없는 호출 옵션. 회사 규칙은 하위 클래스가 덧붙임.

        Args:
            temperature: 샘플링 온도. None이면 보내지 않음.
            reasoning_effort: 추론 강도. None이면 보내지 않음.

        Returns:
            list[str]: 문제 설명. 비면 이상 없음.
        """
        if reasoning_effort is not None and reasoning_effort not in self.reasoning_efforts:
            return [f"{self.id}가 받지 않는 추론 강도입니다: {reasoning_effort!r}"]
        return []


@dataclass(frozen=True)
class OpenAIModel(ChatModel):
    """OpenAI 모델. 추론 모델(reasoning_efforts가 있음)은 temperature 기본값(1)만 받고 0을 거부함."""

    vendor: ClassVar[str] = "openai"

    def option_errors(self, temperature: float | None, reasoning_effort: str | None) -> list[str]:
        errors = super().option_errors(temperature, reasoning_effort)
        if self.reasoning_efforts and temperature is not None:
            errors.append(f"추론 모델 {self.id}에는 temperature를 줄 수 없습니다.")
        return errors


@dataclass(frozen=True)
class GeminiModel(ChatModel):
    """Google Gemini 모델. temperature·추론 강도 둘 다 받음.

    2026-10-14 실호출 (gemini-2.5-flash·pro): json_schema strict 구조화 출력, temperature=0, reasoning_effort="low" 동작.
    캐시 적중은 들쭉날쭉하게 보고됨 (같은 요청 3회 중 1회). 사용량은 LangChain usage_metadata가 비어 게이트웨이 token_usage로 읽음.
    """

    vendor: ClassVar[str] = "google"


@dataclass(frozen=True)
class ClaudeModel(ChatModel):
    """Anthropic Claude 모델. 게이트웨이를 거치면 temperature·추론 강도 둘 다 못 줌.

    2026-10-14 실호출 (claude-haiku-4-5·sonnet-4-5):
        - temperature: 게이트웨이 오류 500/502 ("AsyncMessages.stream() got an unexpected keyword argument 'temperature'")
        - reasoning_effort: 구조화 출력이 도구 강제 호출로 바뀌어 거부됨 ("Thinking may not be enabled when tool_choice forces tool use")
        - 옵션 없이 부르면 json_schema 구조화 출력 동작. 스키마가 도구 정의로 들어가 입력 토큰이 늘어남, 캐시는 공통 필드(cached_prompt_tokens·cache_write_tokens)로 보고됨
    게이트웨이가 고쳐지면 이 규칙을 풀면 됨.
    """

    vendor: ClassVar[str] = "anthropic"

    def option_errors(self, temperature: float | None, reasoning_effort: str | None) -> list[str]:
        errors = []
        if temperature is not None:
            errors.append(f"{self.id}에는 게이트웨이를 거치면 temperature를 줄 수 없습니다.")
        if reasoning_effort is not None:
            errors.append(f"{self.id}의 추론 강도는 구조화 출력과 함께 쓸 수 없습니다.")
        return errors


# 엘리스 단가 = OpenAI 달러 단가 × 약 1,522.5원 (mini: $0.40 / $0.10 / $1.60, 캐시 입력은 입력의 25%)
GPT_41_MINI = OpenAIModel(
    "gpt-4.1-mini",
    Price(input=609.0, cached_input=152.0, output=2436.0),
    price_source="엘리스 ML API 모델 라이브러리 2026-09-07",
)
# 캐시 입력은 라이브러리에 표시 없음. OpenAI 최신 계열 비율(입력의 10%)로 추정
GPT_6_LUNA = OpenAIModel(
    "gpt-6-luna",
    Price(input=152.0, cached_input=15.2, output=761.0),
    price_source="엘리스 ML API 모델 라이브러리 2026-10-14 (캐시 입력은 입력의 10%로 추정)",
    reasoning_efforts=("none", "low", "medium", "high", "xhigh"),
)

CHAT_MODELS = {model.id: model for model in (GPT_41_MINI, GPT_6_LUNA)}


@dataclass(frozen=True)
class DecisionModel:
    """게이트웨이 카탈로그의 판단 모델 1개 (/decisions). temperature·추론 강도 없음.

    Attributes:
        name: 회사 접두어 없는 모델 이름 (예: "jev-latest").
        vendor: 카탈로그 등록명 접두어. 요청·응답 형식도 이걸로 고름 (typesafe·openai).
        price: 1M 토큰당 KRW. 모르면 None (비용 계산 안 함).
        price_source: 단가 출처·확인일.
    """

    name: str
    vendor: str
    price: Price | None
    price_source: str = ""

    @property
    def id(self) -> str:
        """카탈로그 등록명 (예: "typesafe/jev-latest"). 게이트웨이는 접두어 없는 이름을 거부함."""
        return f"{self.vendor}/{self.name}"


# 버전 고정 ID(jev-1.14 등)는 게이트웨이가 404. 실제 버전은 응답 model로 옴
# $0.042 × 약 1,522.5원. 출력 토큰은 0으로 보고됨, 캐시 적중은 늘 0이라 캐시 입력은 입력과 같게 둠
JEV = DecisionModel(
    "jev-latest", "typesafe",
    Price(input=64.0, cached_input=64.0, output=0.0),
    price_source="엘리스 ML API 모델 라이브러리 2026-10-29",
)
# 채팅 Luna와 같은 등록명이라 단가도 같게 둠 (비용 단가표가 등록명 하나에 단가 하나). 판단 출력 토큰은 0으로 보고됨
GPT_6_LUNA_DECISION = DecisionModel("gpt-6-luna", "openai", GPT_6_LUNA.price, price_source=GPT_6_LUNA.price_source)

DECISION_MODELS = {model.id: model for model in (JEV, GPT_6_LUNA_DECISION)}
