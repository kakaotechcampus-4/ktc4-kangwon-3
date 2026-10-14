"""채팅 모델 카탈로그. 게이트웨이에 등록된 모델과 단가 (#279).

새 모델은 ChatModel 상수 하나 + CHAT_MODELS에 넣기.
"""

from dataclasses import dataclass


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
    """게이트웨이 카탈로그의 채팅 모델 1개.

    Attributes:
        id: 카탈로그 등록명 ("openai/" 접두어 포함).
        price: 1M 토큰당 KRW. 모르면 None (비용 계산 안 함).
        price_source: 단가 출처·확인일.
        reasoning_efforts: 받는 추론 강도. 비면 일반 모델, 있으면 추론 모델(temperature 기본값만 받음).
    """

    id: str
    price: Price | None
    price_source: str = ""
    reasoning_efforts: tuple[str, ...] = ()

    @property
    def is_reasoning(self) -> bool:
        return bool(self.reasoning_efforts)


# 엘리스 단가 = OpenAI 달러 단가 × 약 1,522.5원 (mini: $0.40 / $0.10 / $1.60, 캐시 입력은 입력의 25%)
GPT_41_MINI = ChatModel(
    "openai/gpt-4.1-mini",
    Price(input=609.0, cached_input=152.0, output=2436.0),
    price_source="엘리스 ML API 모델 라이브러리 2026-09-07",
)
# 단가는 추론 강도와 무관하게 모델당 하나 (추론 토큰은 출력 토큰으로 과금)
# 캐시 입력은 라이브러리에 표시 없음. OpenAI 최신 계열 비율(입력의 10%)로 추정
GPT_6_LUNA = ChatModel(
    "openai/gpt-6-luna",
    Price(input=152.0, cached_input=15.2, output=761.0),
    price_source="엘리스 ML API 모델 라이브러리 2026-10-14 (캐시 입력은 입력의 10%로 추정)",
    reasoning_efforts=("none", "low", "medium", "high", "xhigh"),
)

CHAT_MODELS = {model.id: model for model in (GPT_41_MINI, GPT_6_LUNA)}
