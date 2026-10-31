"""판단 선택 에이전트 패키지. 선택 에이전트(selection)와 같은 단계를 판단 모델(/decisions)로 구현.

- questions.py: Tool별 예/아니오 질문 (TOOL_QUESTIONS, QUESTIONS)
- rules.py: 판단 모델 없이 정하는 코드 규칙 (rule_reasons)
- thresholds.py: (판단 모델, Tool)별 문턱값 (threshold)
- assemble.py: 규칙·판단 답 → 6개 Tool 선택 결과와 이유 (assemble)
- agent.py: DecisionSelectionAgent — Product → 판단 모델 한 번 → 6개 Tool 선택 (ToolSelectionResponse)
- errors.py: DecisionSelectionFailedError
"""

from .agent import DecisionSelectionAgent
from .assemble import assemble
from .errors import DecisionSelectionFailedError
from .questions import QUESTIONS, TOOL_QUESTIONS
from .rules import rule_reasons
from .thresholds import threshold

__all__ = [
    "QUESTIONS", "TOOL_QUESTIONS", "DecisionSelectionAgent", "DecisionSelectionFailedError", "assemble",
    "rule_reasons", "threshold",
]
