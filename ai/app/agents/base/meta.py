"""에이전트 호출 1건의 실행 정보와 결과 묶음. 파이프라인·평가가 결과와 함께 받음."""

from dataclasses import dataclass
from typing import Generic

from ...schemas.base import StrictModel
from ...usage import CallUsage
from .protocols import ResultT


class AgentRunMeta(StrictModel):
    """에이전트 호출 1건의 실행 정보.

    Attributes:
        component: 에이전트 이름.
        model: 비용 계산용 모델 이름. 모델이 없는 에이전트(규칙 전용 실행)는 None.
        reasoning_effort: 추론 강도. 스텁·주입 모델은 None.
        prompt_name: 시스템 프롬프트 이름.
        prompt_sha256: 프롬프트 지문 (버전 비교용).
        usage: 토큰 사용량. 호출 실패로 모르거나 호출이 없었으면 None.
        cost_krw: 예상 비용(원). 단가를 모르면 None.
        elapsed_ms: 걸린 시간(ms).
        error_type: 실패 원인 예외 이름. 성공이면 None.
        failure_phase: 실패 단계 (call·parsing·finalize). 성공이면 None.
    """

    component: str
    model: str | None = None
    reasoning_effort: str | None = None
    prompt_name: str | None = None
    prompt_sha256: str | None = None
    usage: CallUsage | None = None
    cost_krw: float | None = None
    elapsed_ms: int = 0
    error_type: str | None = None
    failure_phase: str | None = None


@dataclass(frozen=True)
class AgentResult(Generic[ResultT]):
    """에이전트 결과와 실행 정보 묶음 (``BaseAgent.run_with_meta`` 반환값).

    Attributes:
        result: 에이전트 결과.
        meta: 실행 정보.
    """

    result: ResultT
    meta: AgentRunMeta
