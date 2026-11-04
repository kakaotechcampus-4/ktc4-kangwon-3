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
        _ask("ad_certification", "판매자가 인증·승인을 받았다고 내세우는 문구가 있는가 (예: FDA 승인, TSA 인증). "
                                 "스펙표에 인증 이름(CE·FCC·RoHS 등)을 나열만 했으면 해당 없음"),
        _ask("ad_numeric", "판매자 문구에 효과나 지속 시간을 과장할 수 있는 수치 주장이 있는가 (예: 48시간 재생, 보온 24시간). "
                           "용량·크기·출력 같은 규격 표기는 해당 없음"),
        _ask("ad_safety", "판매자가 특정 사용자(어린이·민감 피부 등)에게 안전하거나 적합하다고 단정하는 문구가 있는가 "
                          "(예: 아기 피부에도 안전, 무독성). '안전한 결제' 같은 쇼핑몰 공통 문구는 해당 없음"),
    ),
}

# 한 번에 보내는 전체 질문 (Tool 순서대로)
QUESTIONS: tuple[YesNoQuestion, ...] = tuple(question for group in TOOL_QUESTIONS.values() for question in group)

# 선택 이유에 쓰는 질문별 짧은 설명. 판단 모델에는 안 보냄 (질문 목록 지문과 무관)
QUESTION_LABELS: dict[str, str] = {
    "radio_wireless_comm": "무선 통신 기능",
    "radio_wireless_charging": "무선충전 기능",
    "radio_wireless_shield": "RFID 차단·전자파 차폐 기능",
    "food_contact": "음식·음료에 직접 닿는 용도",
    "food_medical_claim": "질병 치료·신체기능 개선 효과 표현",
    "food_cosmetic_claim": "미용·피부 효과 표현",
    "food_absorbed": "피부·점막에 성분이 흡수·반응할 수 있는 용도",
    "electric_powered": "전기 작동 또는 전지 내장",
    "electric_battery_product": "상품 자체가 전지",
    "electric_heating": "발열 기능",
    "children_target": "만 13세 이하 어린이 대상 표기·광고",
    "children_kind": "완구·학용품·유아용품처럼 어린이가 주로 쓰는 종류",
    "ad_effect": "효능·효과 표현",
    "ad_superlative": "최상급·절대적 표현",
    "ad_certification": "인증·승인 언급",
    "ad_numeric": "효과·지속 시간 수치",
    "ad_safety": "특정 사용자 대상 안전·적합 표현",
}
