"""에이전트 공통 베이스 패키지 (#171 §4 M1).

- agent.py: BaseAgent — 모델 준비·구조화 출력 호출·예외 변환
- parsing.py: 모델 응답 → 출력 스키마 (거절·엄격한 JSON·빈 응답 처리)
- usage_log.py: 호출 1건의 사용량 기록·콘솔 로그
- meta.py: AgentRunMeta — 호출 1건의 실행 정보 (모델·프롬프트 지문·사용량·비용·시간)
- errors.py: AgentError(실패 시 meta 포함)·MissingParsedOutput·ModelFailurePhase
- protocols.py: 공통 타입 — 주입 모델 인터페이스 (ModelLike·StructuredModel), 출력 타입 변수 OutputT
"""

from .agent import BaseAgent
from .errors import AgentError, MissingParsedOutput, ModelFailurePhase
from .meta import AgentRunMeta
from .protocols import ModelLike, StructuredModel

__all__ = [
    "AgentError", "AgentRunMeta", "BaseAgent", "MissingParsedOutput", "ModelFailurePhase", "ModelLike", "StructuredModel",
]
