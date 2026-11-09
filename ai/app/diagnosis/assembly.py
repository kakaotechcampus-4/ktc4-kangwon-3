"""진단 파이프라인 부품 조립. 기동 때 한 번 만들어 모든 진단이 같이 씀.

에이전트·Tool은 실행마다 상태를 새로 만들어서(ToolRun 등) 여러 진단이 동시에 써도 됨.
법제처 조회 경로는 기준일별 캐시를 객체 안에 두므로 한 번만 만들어야 캐시가 공유됨.
"""

from dataclasses import dataclass

from ..agents.extraction import ExtractionAgent
from ..agents.decision_selection import DecisionSelectionAgent
from ..agents.verification import VerificationAgent
from ..pipeline.aggregator import ResultAggregator
from ..pipeline.extraction_step import ExtractionStep
from ..pipeline.runner import SelectionStage, VerificationStage
from ..pipeline.url_source import UrlSourceBuilder
from ..schemas.schemas import ToolName
from ..tools.advertising import AdvertisingTool
from ..tools.advertising.search import evidence_loader as advertising_evidence_loader
from ..tools.base import RegulatoryTool
from ..tools.children import ChildrenTool
from ..tools.children.search import item_search as children_item_search
from ..tools.customs import CustomsTool
from ..tools.customs.search import case_search, evidence_loader as customs_evidence_loader, requirement_lookup
from ..tools.electrical import ElectricalTool
from ..tools.electrical.search import item_search as electrical_item_search
from ..tools.food_drug import FoodDrugTool
from ..tools.food_drug.search import evidence_loader as food_drug_evidence_loader
from ..tools.radio import RadioTool
from ..tools.radio.search import item_search as radio_item_search
from .tracing import TracedImageSplitter


@dataclass(frozen=True)
class PipelineParts:
    """모든 진단이 같이 쓰는 파이프라인 부품.

    Attributes:
        extraction: 진단 입력 → 상품 정보. 재진단이면 이전 추출 결과를 그대로 씀.
        selector: Tool 선택 에이전트 (판단 모델로 고르는 판단 선택 에이전트).
        tools: Tool 6개 (ToolName → 구현).
        aggregator: Tool 결과 → 검증 전 초안.
        verifier: 검증 에이전트.
    """

    extraction: ExtractionStep
    selector: SelectionStage
    tools: dict[ToolName, RegulatoryTool]
    aggregator: ResultAggregator
    verifier: VerificationStage


def build_tools() -> dict[ToolName, RegulatoryTool]:
    """Tool 6개를 만든다. 모델은 Tool 프로필, 조회 경로는 DB 캐시를 먼저 보는 경로.

    Returns:
        dict[ToolName, RegulatoryTool]: ToolName → Tool.

    Raises:
        ConfigError: 모델·키 설정이 없거나 잘못된 경우.
    """
    tools: list[RegulatoryTool] = [
        CustomsTool(case_search=case_search(), requirements=requirement_lookup(),
                    evidence=customs_evidence_loader()),
        RadioTool(item_search=radio_item_search()),
        FoodDrugTool(evidence=food_drug_evidence_loader()),
        ElectricalTool(item_search=electrical_item_search()),
        ChildrenTool(item_search=children_item_search()),
        AdvertisingTool(evidence=advertising_evidence_loader()),
    ]
    return {tool.tool_name: tool for tool in tools}


def build_parts() -> PipelineParts:
    """파이프라인 부품을 만든다. 서버 기동 때 한 번 부름.

    Returns:
        PipelineParts: 에이전트·Tool·추출 단계.

    Raises:
        ConfigError: 모델·키 설정이 없거나 잘못된 경우.
    """
    return PipelineParts(
        # 이미지 자르기는 trace 기록 중에만 전후를 남기는 감싼 것 (동작은 같음)
        extraction=ExtractionStep(ExtractionAgent(), UrlSourceBuilder(), image_splitter=TracedImageSplitter()),
        selector=DecisionSelectionAgent(),
        tools=build_tools(),
        aggregator=ResultAggregator(),
        # 검증만 기본 생성자로는 모델이 없음 (규칙 전용 실행용)
        verifier=VerificationAgent.from_env(),
    )
