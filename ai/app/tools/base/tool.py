"""심사 툴 6개가 따를 공통 호출 규격."""

from abc import ABC
from typing import ClassVar

from ...schemas.agent import ToolSelectionItem
from ...schemas.product import Product
from ...schemas.schemas import ToolName, ToolResult, ToolStatus


class RegulatoryTool(ABC):
    """기관 클라이언트로 자료를 조회하고 ToolResult로 심사 결과를 반환한다.

    선택 확인·SKIPPED는 execute가 맡고, 하위 클래스는 선택된 경우의 실행(_run)만 구현.
    조회 실패를 규제 비대상으로 바꾸지 않으며, 선택 이유도 결과에 보존한다.
    """

    tool_name: ClassVar[ToolName]

    def execute(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """상품 정보와 이 툴의 선택 결정을 받아 실행한다. 미선택은 조회 없이 생략.

        Args:
            product: 추출 에이전트가 만든 상품 정보.
            decision: 이 툴의 선택 결정.

        Returns:
            ToolResult: 미선택이면 SKIPPED, 그 밖에는 _run의 결과.

        Raises:
            ValueError: 다른 툴의 선택 결정을 받은 경우.
        """
        if decision.tool_name is not self.tool_name:
            raise ValueError(f"선택 결정의 Tool 이름({decision.tool_name})이 이 Tool({self.tool_name})과 다릅니다.")
        if not decision.selected:
            return ToolResult(tool_name=self.tool_name, selected=False, selection_reason=decision.reason,
                              status=ToolStatus.SKIPPED)
        return self._run(product, decision)

    def _run(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """선택된 경우의 실행. 모델·자료 조회 실패는 예외로 전파해 Executor가 기록한다.

        Args:
            product: 추출 에이전트가 만든 상품 정보.
            decision: 이 툴의 선택 결정 (selected=True).

        Returns:
            ToolResult: 심사 결과.

        Raises:
            NotImplementedError: 하위 Tool이 구현하지 않은 경우.
        """
        # execute를 통째로 덮어쓰는 테스트용 가짜 Tool이 있어 추상 메서드로 두지 않음
        raise NotImplementedError
