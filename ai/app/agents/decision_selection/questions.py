"""판단 선택 질문 목록. Tool마다 상품 사실을 묻는 예/아니오 질문, 답 확률과 문턱값 비교는 조립 단계 몫."""

from ...schemas.clients.decision_request import YesNoQuestion
from ...schemas.schemas import ToolName

# 모든 질문 앞에 붙이는 판단 대상 설명
SUBJECT_NOTE = "판단 대상은 해외 직구 상품에서 추출한 정보(JSON)다. 상품명·카테고리·listing_text 등 적힌 내용을 근거로 답한다. 질문: "


def _ask(name: str, text: str) -> YesNoQuestion:
    """판단 대상 설명을 앞에 붙인 예/아니오 질문을 만든다.

    Args:
        name: 질문 이름.
        text: 질문 문장.

    Returns:
        YesNoQuestion: 판단 모델에 보낼 질문.
    """
    return YesNoQuestion(name=name, instructions=SUBJECT_NOTE + text)


# 통관은 항상 선택이라 질문 없음. 질문 문장은 10-29 선택 실험 그대로
TOOL_QUESTIONS: dict[ToolName, tuple[YesNoQuestion, ...]] = {
    ToolName.RADIO: (
        _ask("radio_wireless_comm", "이 상품에 블루투스·WiFi·RF 리모컨 같은 무선 통신 기능이 있는가"),
        _ask("radio_wireless_charging", "이 상품에 무선충전 기능이 있는가"),
        _ask("radio_wireless_shield", "이 상품에 RFID 차단·전자파 차폐 기능이 있는가"),
    ),
    ToolName.FOOD_DRUG: (
        _ask("food_contact", "이 상품이 음식·음료에 직접 닿는 용도인가 (식기·조리도구·용기 등)"),
        _ask("food_medical_claim", "판매자가 질병 치료·예방이나 신체기능 개선 효과를 표방하는가"),
        _ask("food_cosmetic_claim", "판매자가 미용·피부 효과를 표방하는가"),
        _ask("food_absorbed", "화장품·의료기기·구강용품·위생용품처럼 피부·점막에 성분이 흡수·반응할 수 있는 용도의 상품인가"),
    ),
    ToolName.ELECTRICAL: (
        _ask("electric_powered", "이 상품이 전기로 작동하거나 전지가 들어 있는가"),
        _ask("electric_battery_product", "이 상품 자체가 전지인가 (보조배터리·건전지 등)"),
        _ask("electric_heating", "발열이 이 상품의 기능인가"),
    ),
    ToolName.CHILDREN: (
        _ask("children_target", "판매자가 만 13세 이하 어린이를 사용 대상으로 표기하거나 광고하는가"),
        _ask("children_kind", "완구·학용품·유아용품처럼 어린이가 주로 쓰는 종류의 상품인가"),
    ),
    ToolName.LABEL_AD: (
        _ask("ad_effect", "판매자 문구에 효능·효과를 표방하는 표현이 있는가 (예: 혈액순환 개선, 숙면 유도)"),
        _ask("ad_superlative", "판매자 문구에 최상급·절대적 표현이 있는가 (예: 최고, 완벽 차단, 100%)"),
        _ask("ad_certification", "판매자 문구에 검증되지 않았을 수 있는 인증 표방이 있는가 (예: FDA 승인, TSA 인증)"),
        _ask("ad_numeric", "판매자 문구에 과장 가능성이 있는 객관적 수치 주장이 있는가 (예: 48시간 재생, 보온 24시간)"),
    ),
}

# 한 번에 보내는 전체 질문 (Tool 순서대로)
QUESTIONS: tuple[YesNoQuestion, ...] = tuple(question for group in TOOL_QUESTIONS.values() for question in group)
