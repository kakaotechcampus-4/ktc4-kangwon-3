"""단계 다시 실행 (로컬 trace CLI용). 이전 trace에 남은 단계 output으로 앞 단계를 건너뛰고 지정한 단계부터 돌림.

첫 회차(round 0)에서 시작 단계 앞의 단계만 저장한 output을 씀. 재실행 회차는 앞 결과에 따라 달라져 항상 실제로 돎.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from ..observability.trace import trace_finish
from ..schemas.agent import ToolSelectionResponse
from ..schemas.pipeline import SelectionResult
from ..schemas.product import Product
from ..schemas.schemas import DraftAssessment, VerificationResult
from ..schemas.session import DiagnosisInput

# 파이프라인 단계 순서 (trace 단계 kind)
STAGES = ("extraction", "selection", "tool_execution", "aggregation", "verification")
_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "extraction": Product,
    "selection": ToolSelectionResponse,
    "tool_execution": SelectionResult,
    "aggregation": DraftAssessment,
    "verification": VerificationResult,
}


class ReplayError(ValueError):
    """다시 실행할 수 없는 trace (시작 단계 앞 단계의 output이 없는 경우 등)."""


class ReplayStopped(Exception):
    """시작 단계 하나만 다시 돌리고 멈춤 (only). 진단 함수 밖까지 올라감.

    Attributes:
        stage: 멈춘 단계.
    """

    def __init__(self, stage: str) -> None:
        super().__init__(f"{stage} 단계만 다시 실행하고 멈춤")
        self.stage = stage


@dataclass(frozen=True)
class StageReplay:
    """단계 다시 실행 설정.

    Attributes:
        outputs: 이전 trace의 첫 회차 단계 output (단계 → JSON).
        start: 실제로 돌리기 시작할 단계.
        only: 시작 단계 하나만 돌리고 멈출지.
    """

    outputs: dict[str, Any]
    start: str
    only: bool = False

    @classmethod
    def from_trace(cls, trace: dict[str, Any], start: str, only: bool = False) -> "StageReplay":
        """이전 trace(run-N.json 내용)에서 다시 실행 설정을 만든다.

        Args:
            trace: 이전 실행의 trace.
            start: 시작 단계.
            only: 시작 단계 하나만 돌릴지.

        Returns:
            StageReplay: 다시 실행 설정.

        Raises:
            ReplayError: 모르는 단계이거나 시작 단계 앞 단계의 output이 없는 경우.
        """
        if start not in STAGES:
            raise ReplayError(f"모르는 단계입니다: {start} (가능: {', '.join(STAGES)})")
        outputs = {step["kind"]: step["output"] for step in trace.get("steps", [])
                   if step.get("kind") in STAGES and step.get("round", 0) == 0 and "output" in step}
        missing = [kind for kind in STAGES[:STAGES.index(start)] if kind not in outputs]
        if missing:
            raise ReplayError(f"이전 trace에 앞 단계 결과가 없습니다: {', '.join(missing)}")
        return cls(outputs, start, only)

    def saved(self, stage: str) -> BaseModel | None:
        """건너뛸 단계면 저장한 output. 시작 단계부터는 None.

        Args:
            stage: 단계.

        Returns:
            BaseModel | None: 저장한 output.

        Raises:
            ReplayError: 저장한 output이 지금 스키마와 맞지 않는 경우.
        """
        if STAGES.index(stage) >= STAGES.index(self.start):
            return None
        try:
            return _OUTPUT_MODELS[stage].model_validate(self.outputs[stage])
        except ValidationError as exc:
            raise ReplayError(f"이전 trace의 {stage} 결과를 지금 스키마로 읽지 못했습니다: {exc}") from exc

    def done(self, stage: str) -> None:
        """단계 하나를 마쳤음. 시작 단계만 돌리는 설정이면 결말을 남기고 멈춤.

        Args:
            stage: 마친 단계.

        Raises:
            ReplayStopped: only이고 시작 단계를 마친 경우.
        """
        if self.only and stage == self.start:
            trace_finish("stopped", stage=stage)
            raise ReplayStopped(stage)


def replay_input(trace: dict[str, Any]) -> DiagnosisInput:
    """이전 trace의 실행 입력 (추출 단계 input).

    Args:
        trace: 이전 실행의 trace.

    Returns:
        DiagnosisInput: 실행 입력.

    Raises:
        ReplayError: 추출 단계 input이 없거나 읽지 못한 경우.
    """
    extraction = next((step for step in trace.get("steps", []) if step.get("kind") == "extraction"), None)
    if extraction is None or "input" not in extraction:
        raise ReplayError("이전 trace에 실행 입력(추출 단계 input)이 없습니다")
    try:
        return DiagnosisInput.model_validate(extraction["input"])
    except ValidationError as exc:
        raise ReplayError(f"이전 trace의 실행 입력을 읽지 못했습니다: {exc}") from exc
