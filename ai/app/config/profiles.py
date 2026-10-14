"""모델 프로필. 에이전트가 고르는 호출 조건(모델 + temperature 또는 추론 강도) (#279).

새 조합은 MODEL_PROFILES에 ModelProfile 한 줄.
잘못된 조합(추론 모델에 temperature, 지원하지 않는 추론 강도)은 import 시점에 실패함.
"""

from dataclasses import asdict, dataclass

from .catalog import GPT_6_LUNA, GPT_41_MINI, ChatModel


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
