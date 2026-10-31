"""판단 선택 문턱값. Tool 질문 중 하나라도 "예" 확률이 문턱값 이상이면 선택.

확률 분포가 모델마다 달라 (판단 모델, Tool)별로 둠 (Luna는 0·1 쪽으로 쏠림, Jev는 0.1~0.7대).
질문 문장이 바뀌면 분포도 바뀌므로 질문 목록과 같이 둠.
"""

from ...config.catalog import GPT_6_LUNA_DECISION, JEV
from ...schemas.schemas import ToolName
from .questions import TOOL_QUESTIONS

# 판단 모델 등록명 → Tool별 문턱값. 질문 있는 Tool 전부 필요
THRESHOLDS: dict[str, dict[ToolName, float]] = {
    # 10-29 선택 실험에서 규칙+판단 조합이 가장 적게 놓친 값
    JEV.id: {
        **{tool: 0.3 for tool in TOOL_QUESTIONS},
        # 10-31 #433 가상 상품: 대상 0.17~0.78, 비대상 0.04~0.05 (놓치는 쪽이 더 위험해 낮게)
        ToolName.CHILDREN: 0.15,
    },
    # 임시값. 평가 러너로 측정한 뒤 조정
    GPT_6_LUNA_DECISION.id: {tool: 0.5 for tool in TOOL_QUESTIONS},
}


def threshold(model: str, tool: ToolName) -> float:
    """판단 모델과 Tool의 문턱값.

    Args:
        model: 판단 모델 등록명 (예: "typesafe/jev-latest").
        tool: 질문 있는 Tool.

    Returns:
        float: 문턱값.

    Raises:
        ValueError: 문턱값이 정해지지 않은 판단 모델이나 Tool인 경우.
    """
    try:
        return THRESHOLDS[model][tool]
    except KeyError as exc:
        raise ValueError(f"판단 선택 문턱값이 정해지지 않았습니다: {model} / {tool}") from exc
