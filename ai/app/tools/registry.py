"""선택 결과의 툴 이름을 구현 클래스에 연결한다. 등록만으로 실행하지 않는다."""

from .advertising import AdvertisingTool
from .base import RegulatoryTool
from .children import ChildrenTool
from .customs import CustomsTool
from .electrical import ElectricalTool
from .food_drug import FoodDrugTool
from .radio import RadioTool
from ..schemas.schemas import ToolName

# 기관 API 클라이언트 의존성 주입과 인스턴스 생성은 후속 실행부에서 담당한다.
TOOL_REGISTRY: dict[ToolName, type[RegulatoryTool]] = {
    ToolName.CUSTOMS: CustomsTool,
    ToolName.RADIO: RadioTool,
    ToolName.FOOD_DRUG: FoodDrugTool,
    ToolName.ELECTRICAL: ElectricalTool,
    ToolName.CHILDREN: ChildrenTool,
    ToolName.LABEL_AD: AdvertisingTool,
}
