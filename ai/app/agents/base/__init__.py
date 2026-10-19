"""에이전트 공통 베이스 패키지 (#171 §4 M1).

- agent.py: BaseAgent — 공통 실행 인터페이스(run·run_with_meta, 하위는 _build_messages·_subject_id 구현)·모델 호출·예외 변환
- parsing.py: 모델 응답 → 출력 스키마 (거절·엄격한 JSON·빈 응답 처리)
- usage_log.py: 호출 1건의 사용량 기록·콘솔 로그
- meta.py: AgentRunMeta(호출 1건의 실행 정보)·AgentResult(결과 + 실행 정보)
- errors.py: AgentError(실패 시 meta 포함)·MissingParsedOutput·ModelFailurePhase
- protocols.py: 공통 타입 — 주입 모델 인터페이스 (ModelLike·StructuredModel), 타입 변수 InputT·OutputT·ResultT
"""

from ...usage import record  # 호환용: 열린 Tool PR이 app.agents.base.record를 바꿔치기함. 머지 후 정리
from .agent import BaseAgent
from .errors import AgentError, MissingParsedOutput, ModelFailurePhase
from .meta import AgentResult, AgentRunMeta
from .protocols import ModelLike, StructuredModel

__all__ = [
    "AgentError", "AgentResult", "AgentRunMeta", "BaseAgent", "MissingParsedOutput", "ModelFailurePhase",
    "ModelLike", "StructuredModel", "record",
]
