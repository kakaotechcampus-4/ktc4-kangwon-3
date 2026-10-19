"""에이전트 공통 베이스 패키지 (#171 §4 M1).

- agent.py: BaseAgent — 모델 준비·구조화 출력 호출·예외 변환
- parsing.py: 모델 응답 → 출력 스키마 (거절·엄격한 JSON·빈 응답 처리)
- usage_log.py: 호출 1건의 사용량 기록·콘솔 로그
- errors.py: AgentError·MissingParsedOutput·ModelFailurePhase
- protocols.py: 주입 모델의 최소 인터페이스 (ModelLike·StructuredModel)
"""

from .agent import BaseAgent
from .errors import AgentError, MissingParsedOutput, ModelFailurePhase
from .protocols import ModelLike, StructuredModel

__all__ = ["AgentError", "BaseAgent", "MissingParsedOutput", "ModelFailurePhase", "ModelLike", "StructuredModel"]
