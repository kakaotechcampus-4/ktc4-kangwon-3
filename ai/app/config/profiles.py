"""모델 프로필. 에이전트가 고르는 호출 조건(모델 + temperature 또는 추론 강도) (#279).

새 조합은 MODEL_PROFILES에 ModelProfile 한 줄.
모델이 받지 않는 옵션 조합(회사별 규칙은 catalog.py)은 import 시점에 실패함.
"""

from dataclasses import asdict, dataclass

from .catalog import GPT_6_LUNA, GPT_41_MINI, ChatModel


@dataclass(frozen=True)
class ModelProfile:
    """에이전트가 고르는 모델 호출 조건. None인 값은 모델에 보내지 않음.

    Attributes:
        name: 프로필 이름 (AGENT_PROFILES·TOOL_PROFILES·*_MODEL_PROFILE 환경변수 값).
        model: 호출할 모델.
        temperature: 샘플링 온도.
        reasoning_effort: 추론 강도.
        note: 이 조합을 둔 이유 (실측 결과 등).

    Raises:
        ValueError: 모델이 받지 않는 temperature·추론 강도를 준 경우 (ChatModel.option_errors).
    """

    name: str
    model: ChatModel
    temperature: float | None = None
    reasoning_effort: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        errors = self.model.option_errors(self.temperature, self.reasoning_effort)
        if errors:
            raise ValueError(f"{self.name}: {' / '.join(errors)}")

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

# 에이전트별 기본 프로필. 키는 BaseAgent.component_name
# AGENT_{이름}_MODEL_PROFILE 환경변수로 바꿀 수 있음 (예: AGENT_EXTRACTION_MODEL_PROFILE=luna-low)
AGENT_PROFILES = {
    "extraction": "mini",
    "selection": "mini",
    "verification": "mini",
}

# Tool별 기본 프로필. 키는 ToolName 값. 에이전트와 이름이 겹쳐도 따로 고르도록 표를 나눔
# TOOL_{이름}_MODEL_PROFILE 환경변수로 바꿀 수 있음 (예: TOOL_ELECTRICAL_SAFETY_MODEL_PROFILE=luna-low)
TOOL_PROFILES = {
    "electrical_safety": "mini",
}
