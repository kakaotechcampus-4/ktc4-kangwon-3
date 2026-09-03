"""일반 심사 클래스를 LLM이 호출할 수 있는 LangChain 툴로 감싼다."""

from langchain_core.tools import BaseTool, tool
from pydantic import Field

from ..schemas.agent import ToolSelectionItem
from ..schemas.base import StrictModel
from ..schemas.product import Product
from ..schemas.schemas import ToolName, ToolResult
from .base import RegulatoryTool


TOOL_DESCRIPTIONS = {
    ToolName.CUSTOMS: "현재 상품의 통관 요건, HS 후보와 필요 서류를 확인한다.",
    ToolName.RADIO: "현재 상품의 무선 통신·충전·차폐 등 전파 관련 특성과 요건을 심사한다.",
    ToolName.FOOD_DRUG: "현재 상품의 식품 접촉·미용·의료 표방·성분 등 식약 관련 요건을 심사한다.",
    ToolName.ELECTRICAL: "현재 상품의 전기 사용·배터리·발열 등 전안법 관련 요건을 심사한다.",
    ToolName.CHILDREN: "현재 상품의 표시 연령·광고 대상 등 어린이제품 관련 요건을 심사한다.",
    ToolName.LABEL_AD: "현재 상품의 판매 문구에서 표시광고 관련 주의 표현과 근거를 확인한다.",
}


class ToolCallInput(StrictModel):
    """상품은 실행부에서 주입하므로 LLM은 호출 이유만 입력한다."""

    reason: str = Field(min_length=1, description="상품의 어떤 근거로 이 심사를 요청하는가")


def build_langchain_tools(
    product: Product, implementations: dict[ToolName, RegulatoryTool],
) -> list[BaseTool]:
    if set(implementations) != set(ToolName):
        raise ValueError("6개 심사 툴 구현이 모두 등록되어야 합니다.")
    # 모델이 상품 사실을 함수 인자로 재작성하지 않게 원래 상품을 보관한다.
    snapshot = product.model_copy(deep=True)

    def wrap(name: ToolName, implementation: RegulatoryTool) -> BaseTool:
        if implementation.tool_name != name:
            raise ValueError("등록한 툴 이름과 구현의 tool_name이 일치하지 않습니다.")

        @tool(
            name.value, description=TOOL_DESCRIPTIONS[name],
            args_schema=ToolCallInput, response_format="content_and_artifact",
        )
        def execute(reason: str) -> tuple[str, ToolResult]:
            decision = ToolSelectionItem(tool_name=name, selected=True, reason=reason)
            result = implementation.execute(snapshot.model_copy(deep=True), decision)
            result = ToolResult.model_validate(result)
            if result.tool_name != name or not result.selected:
                raise ValueError("실행한 툴과 반환한 결과의 식별 정보가 다릅니다.")
            # LLM에는 직렬화한 내용만, 실행부에는 원래 ToolResult를 artifact로 돌려준다.
            # 미구현 오류·예상하지 못한 예외는 성공으로 바꾸지 않고 호출자에게 전파한다.
            return result.model_dump_json(exclude={"raw_response"}), result

        return execute

    return [wrap(name, implementations[name]) for name in ToolName]
