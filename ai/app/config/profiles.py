"""모델 프로필. 에이전트가 고르는 호출 조건(모델 + temperature 또는 추론 강도) (#279).

새 조합은 MODEL_PROFILES에 ModelProfile 한 줄.
모델이 받지 않는 옵션 조합(회사별 규칙은 catalog.py)은 import 시점에 실패함.

판단 모델(/decisions)은 DECISION_PROFILES·AGENT_DECISION_PROFILES로 따로 고름 (호출 옵션 없음).
"""

from dataclasses import asdict, dataclass

from .catalog import GPT_6_LUNA, GPT_6_LUNA_DECISION, GPT_41_MINI, JEV, ChatModel, DecisionModel


@dataclass(frozen=True)
class ModelProfile:
    """에이전트가 고르는 모델 호출 조건. None인 값은 모델에 보내지 않음.

    Attributes:
        name: 프로필 이름 (AGENT_PROFILES·TOOL_PROFILES·MODEL_PROFILE_OVERRIDES 값).
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
# MODEL_PROFILE_OVERRIDES 환경변수로 잠깐 바꿀 수 있음 (예: agent.extraction=luna-low)
AGENT_PROFILES = {
    "extraction": "mini",
    "selection": "mini",
    "verification": "mini",
    # 썸네일 일괄 분류. 글자를 옮겨 적지 않고 종류만 골라 작은 모델로 충분
    "image_triage": "mini",
}

# Tool별 기본 프로필. 키는 ToolName 값. 에이전트와 이름이 겹쳐도 따로 고르도록 표를 나눔
# MODEL_PROFILE_OVERRIDES 환경변수로 잠깐 바꿀 수 있음 (예: tool.electrical_safety=luna-low)
# Tool 안에서 BaseAgent를 쓰면 model_profile = ("tool", ToolName 값)으로 이 표를 씀
TOOL_PROFILES = {
    "electrical_safety": "mini",
    "labeling_advertising_detection": "mini",
    "children_product_safety": "mini",
    "radio_compliance": "mini",
    "customs_requirements": "mini",
    "food_drug_safety": "mini",
}


@dataclass(frozen=True)
class DecisionProfile:
    """에이전트가 고르는 판단 모델.

    Attributes:
        name: 프로필 이름 (AGENT_DECISION_PROFILES 값).
        model: 호출할 판단 모델.
        note: 이 모델을 둔 이유 (실측 결과 등).
    """

    name: str
    model: DecisionModel
    note: str = ""


# 팀 공용 크레딧으로 의도하지 않은 모델을 호출하지 않도록 여기 있는 프로필만 허용
DECISION_PROFILES = {profile.name: profile for profile in (
    DecisionProfile("jev", JEV),
    DecisionProfile("luna", GPT_6_LUNA_DECISION),
)}

# 판단 모델을 쓰는 에이전트별 프로필. 키는 BaseAgent.component_name. 없는 에이전트는 판단 모델을 안 씀
AGENT_DECISION_PROFILES: dict[str, str] = {
    # 10-29 선택 실험 기준. Luna와 비교 측정 후 확정
    "decision_selection": "jev",
}
