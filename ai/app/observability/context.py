"""공통 실행 컨텍스트 (#171 AI_COMMON_CONTRACT.md §2)."""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RunType(StrEnum):
    PRODUCTION = "production"
    EVALUATION = "evaluation"
    TEST = "test"


class PipelineStage(StrEnum):
    PIPELINE = "pipeline"
    EXTRACTION = "extraction"
    SELECTION = "selection"
    TOOL_EXECUTION = "tool_execution"
    AGGREGATION = "aggregation"
    VERIFICATION = "verification"
    FINALIZATION = "finalization"


class ExecutionContext(BaseModel):
    """실행 한 건의 식별 정보. 진입점이 만들고 하위 구성 요소는 전달만 함.

    Attributes:
        run_id: 진입점이 생성. 하위 구성 요소에서 재생성 금지.
        product_id: 상품 요청 ID. 평가에서는 Fixture의 상품 ID.
        run_type: production / evaluation / test.
        diagnosis_id: 운영 진단서 요청은 BE ID. 단독 평가·테스트는 None.
        retry_round: 업무적 재실행 회차. 0부터 시작.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    run_type: RunType
    diagnosis_id: str | None = None
    retry_round: int = Field(default=0, ge=0, strict=True)

    @classmethod
    def start(
        cls,
        *,
        product_id: str,
        run_type: RunType,
        diagnosis_id: str | None = None,
    ) -> "ExecutionContext":
        """새 실행의 컨텍스트를 만든다.

        Args:
            product_id: 상품 요청 ID.
            run_type: 실행 종류.
            diagnosis_id: 진단서 ID. 단독 평가·테스트는 None.

        Returns:
            ExecutionContext: 새 run_id, 회차 0.
        """
        return cls(
            run_id=str(uuid4()),
            diagnosis_id=diagnosis_id,
            product_id=product_id,
            run_type=run_type,
        )

    def next_round(self) -> "ExecutionContext":
        """회차만 1 올린 새 컨텍스트를 만든다. 실행 가능 횟수 검증은 Pipeline 책임.

        Returns:
            ExecutionContext: 식별 정보는 같고 retry_round만 1 증가.
        """
        values = self.model_dump()
        values["retry_round"] = self.retry_round + 1
        return type(self).model_validate(values)
