"""선택 에이전트 패키지.

- agent.py: SelectionAgent — Product → 6개 심사 도메인 선택 (ToolSelectionResponse)
- prompt.md: 시스템 프롬프트
"""

from .agent import PROMPT_PATH, SelectionAgent, SelectionFailedError

__all__ = ["PROMPT_PATH", "SelectionAgent", "SelectionFailedError"]
