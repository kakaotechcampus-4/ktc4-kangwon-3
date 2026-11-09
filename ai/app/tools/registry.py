"""선택 결과의 툴 이름을 구현 클래스에 연결한다. 등록만으로 실행하지 않는다."""

from .advertising import AdvertisingTool
from .base import RegulatoryTool
from .children import ChildrenTool
from .customs import CustomsTool
from .electrical import ElectricalTool
from .food_drug import FoodDrugTool
from .radio import RadioTool
from ..schemas.schemas import ToolName

# 모델 판단과 상관없이 항상 실행하는 Tool (#588). 실상품 평가에서 모델이 표시광고를 고른 회차가 18%뿐이었고,
# 표시광고는 결과 상태 계산에서 빠져 있어(results/status.py) 오경고가 진단 결론을 바꾸지 않는다.
ALWAYS_RUN_TOOLS = frozenset({ToolName.LABEL_AD})
ALWAYS_RUN_REASON = "판매 문구의 표시·광고 표현은 모든 상품에서 확인합니다."

# 기관 API 클라이언트 의존성 주입과 인스턴스 생성은 후속 실행부에서 담당한다.
TOOL_REGISTRY: dict[ToolName, type[RegulatoryTool]] = {
    ToolName.CUSTOMS: CustomsTool,
    ToolName.RADIO: RadioTool,
    ToolName.FOOD_DRUG: FoodDrugTool,
    ToolName.ELECTRICAL: ElectricalTool,
    ToolName.CHILDREN: ChildrenTool,
    ToolName.LABEL_AD: AdvertisingTool,
}
