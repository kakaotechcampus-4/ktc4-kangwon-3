"""채팅 모델 카탈로그와 모델 프로필 (#279).

두 층으로 나눔.
    - ChatModel: 게이트웨이 카탈로그의 모델 1개. 단가·추론 모델 여부를 가짐
    - ModelProfile: 에이전트가 고르는 호출 조건(모델 + temperature 또는 추론 강도)

추가 방법
    - 새 모델: ChatModel 상수 하나 + CHAT_MODELS에 넣기
    - 새 조합: MODEL_PROFILES에 ModelProfile 한 줄
잘못된 조합(추론 모델에 temperature, 지원하지 않는 추론 강도)은 import 시점에 실패함.
"""

from dataclasses import asdict, dataclass


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


@dataclass(frozen=True)
class ModelProfile:
    """에이전트가 고르는 모델 호출 조건. None인 값은 모델에 보내지 않음.

    Attributes:
        name: 프로필 이름 (AGENT_PROFILES·{에이전트}_MODEL_PROFILE 값).
        model: 호출할 모델.
        temperature: 샘플링 온도. 추론 모델은 None만.
        reasoning_effort: 추론 강도. 추론 모델만.
        note: 이 조합을 둔 이유 (실측 결과 등).

    Raises:
        ValueError: 추론 모델에 temperature를 주거나, 모델이 받지 않는 추론 강도를 준 경우.
    """

    name: str
    model: ChatModel
    temperature: float | None = None
    reasoning_effort: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        # 추론 모델은 temperature=0을 거부함
        if self.model.is_reasoning and self.temperature is not None:
            raise ValueError(f"{self.name}: 추론 모델 {self.model.id}에는 temperature를 줄 수 없습니다.")
        if self.reasoning_effort is not None and self.reasoning_effort not in self.model.reasoning_efforts:
            raise ValueError(f"{self.name}: {self.model.id}가 받지 않는 추론 강도입니다: {self.reasoning_effort!r}")

    def metadata(self) -> dict:
        """러너 메타·사용량 기록에 남길 프로필 정보.

        Returns:
            dict: profile, model, temperature, reasoning_effort, price_krw_per_1m, price_source.
        """
        return {
            "profile": self.name,
            "model": self.model.id,
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            "price_krw_per_1m": asdict(self.model.price) if self.model.price else None,
            "price_source": self.model.price_source or None,
        }


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

# 팀 공용 크레딧으로 의도하지 않은 모델을 호출하지 않도록 여기 있는 프로필만 허용
MODEL_PROFILES = {profile.name: profile for profile in (
    ModelProfile("mini", GPT_41_MINI, temperature=0),
    ModelProfile("luna-low", GPT_6_LUNA, reasoning_effort="low"),
    ModelProfile("luna-medium", GPT_6_LUNA, reasoning_effort="medium"),
)}

# 에이전트별 기본 프로필. {에이전트}_MODEL_PROFILE 환경변수로 바꿀 수 있음 (예: EXTRACTION_MODEL_PROFILE)
AGENT_PROFILES = {
    "extraction": "mini",
    "selection": "mini",
    "verification": "mini",
}
