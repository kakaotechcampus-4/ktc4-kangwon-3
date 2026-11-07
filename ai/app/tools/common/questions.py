"""판매자에게 묻는 질문 문장과 도움말 카탈로그.

질문은 "무엇을 확인해야 하는지"를, 도움말은 "어떻게 답하면 되는지"를 예시와 함께 적는다 (테스트 피드백: 질문만으로는
무엇을 답해야 할지 헷갈림). 같은 조건은 어느 Tool이 묻든 같은 문장을 쓴다. 진단 단계가 문장이 같은 질문을 하나로 합치고
(diagnosis/job.py), 지난 회차 질문도 문장으로 찾아 다시 묻지 않기 때문.

Tool 결과의 부족한 정보(missing_information)는 문장 목록이라 도움말을 따로 싣지 못한다. 그래서 질문 문장을 키로 도움말을
되찾는다(help_text). 질문 문장을 바꿀 때는 이 카탈로그만 바꾸면 된다.

검증 모델도 질문을 만든다. 같은 조건을 말만 바꿔 다시 묻지 않도록 모델 질문에는 조건 필드(topic)를 붙이고, 검증 에이전트가
Tool이 이미 묻는 필드·판매자가 지난 회차에 답한 필드(field_for·answered_questions)면 버린다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SellerQuestion:
    """판매자 질문 하나.

    Attributes:
        question: 무엇을 확인해야 하는지. 결과 안내문(presenter)에도 그대로 실리므로 서술형으로 적는다.
        help: 어떻게 답하면 되는지. 예시를 들고 끝은 "~ 주세요".
    """

    question: str
    help: str


# 조건 필드 → 질문. 필드 이름은 Tool의 field_labels 키와 같다.
QUESTIONS: dict[str, SellerQuestion] = {
    # 공통
    "product_type": SellerQuestion(
        "어떤 제품인지(제품 종류) 확인이 필요합니다.",
        "예: 탁상용 선풍기, 블루투스 이어폰, 유아용 식판처럼 어디에 쓰는 무슨 물건인지 적어 주세요.",
    ),
    "material": SellerQuestion(
        "제품의 주된 재질(소재) 확인이 필요합니다.",
        "예: 플라스틱(ABS), 스테인리스, 면 100%, 천연가죽. 여러 재질이면 많이 쓰인 순서로 적어 주세요.",
    ),
    "intended_use": SellerQuestion(
        "제품을 어디에 어떻게 쓰는지(용도) 확인이 필요합니다.",
        "예: 주방에서 음식을 담는 용도, 피부에 바르는 용도, 책상 위 장식용. 몸이나 음식에 닿는지도 함께 적어 주세요.",
    ),
    # 통관
    "function": SellerQuestion(
        "제품에 어떤 기능이 있는지 확인이 필요합니다.",
        "예: 회전, 풍량 3단 조절, 타이머, 블루투스 연결처럼 기능을 하나씩 나열해 주세요.",
    ),
    "composition": SellerQuestion(
        "상자에 함께 들어 있는 구성품 확인이 필요합니다.",
        "예: 본체 1개, USB 케이블, 어댑터, 교체용 필터 2개처럼 함께 오는 것을 모두 적어 주세요.",
    ),
    # 전기용품
    "power_source": SellerQuestion(
        "제품이 어떤 전원으로 작동하는지(전원 방식) 확인이 필요합니다.",
        "예: 콘센트에 꽂아 사용(AC 220V), USB 충전, AA 건전지, 충전식 배터리 내장. 어댑터가 함께 오면 그것도 적어 주세요.",
    ),
    "rated_voltage": SellerQuestion(
        "제품의 정격 전압 확인이 필요합니다.",
        "예: AC 220V, DC 5V, 3.7V. 제품 뒷면 라벨이나 어댑터, 상세페이지 사양표에 적힌 전압을 그대로 적어 주세요.",
    ),
    "rated_power": SellerQuestion(
        "제품의 정격 소비전력 확인이 필요합니다.",
        "예: 45W, 1200W. 제품 라벨이나 상세페이지 사양표에 적힌 값을 그대로 적어 주세요.",
    ),
    "battery_only": SellerQuestion(
        "제품이 건전지·충전지로만 동작하나요, 아니면 전원 코드·어댑터를 꽂아 쓰나요?",
        "건전지·충전지로만 쓰면 '배터리만', 코드나 어댑터를 꽂아 쓰거나 둘 다 되면 '코드·어댑터'라고 답해 주세요.",
    ),
    "adapter_included": SellerQuestion(
        "전원 어댑터가 상품에 포함되는지 확인이 필요합니다.",
        "어댑터가 함께 오면 '포함', 케이블만 오거나 어댑터가 없으면 '미포함'이라고 답해 주세요. 어댑터에 적힌 출력(예: 5V 2A)도 있으면 적어 주세요.",
    ),
    # 전파
    "wireless_feature": SellerQuestion(
        "제품에 무선 기능이 있는지, 있다면 어떤 기능인지 확인이 필요합니다.",
        "예: 블루투스, Wi-Fi, 무선충전, RF 리모컨, GPS. 무선 기능이 전혀 없으면 '없음'이라고 적어 주세요.",
    ),
    "frequency": SellerQuestion(
        "제품이 사용하는 주파수 확인이 필요합니다.",
        "예: 2.4GHz, 5GHz, 433MHz. 상세페이지 사양표나 제품 라벨에 적힌 값을 그대로 적어 주세요.",
    ),
    "output_power": SellerQuestion(
        "무선 송신 출력 확인이 필요합니다.",
        "예: 10mW, 20dBm. 상세페이지 사양표나 제품 라벨에 적힌 값을 그대로 적어 주세요.",
    ),
    # 어린이제품
    "target_age": SellerQuestion(
        "사용 대상 연령 확인이 필요합니다.",
        "예: 만 3세 이상, 36개월 미만, 8세 이상, 성인용. 상세페이지나 포장에 적힌 권장 연령을 그대로 적어 주세요.",
    ),
    # 식약
    "food_contact": SellerQuestion(
        "음식이나 음료에 직접 닿는 용도(먹을 때 쓰거나 담는 것, 조리·보관에 쓰는 것)인가요?",
        "컵·접시·도시락·조리도구·물병처럼 음식이나 음료가 닿는 물건이면 '예', 음식과 상관없으면 '아니요'라고 답해 주세요.",
    ),
    "edible": SellerQuestion(
        "사람이 먹거나 마시는 제품인가요?",
        "영양제·차·간식처럼 먹거나 마시는 제품이면 '예', 아니면 '아니요'라고 답해 주세요.",
    ),
    "skin_applied": SellerQuestion(
        "피부·모발 등 몸에 바르거나 뿌려 쓰는 제품인가요?",
        "로션·샴푸·미스트·연고처럼 몸에 바르거나 뿌리는 제품이면 '예', 아니면 '아니요'라고 답해 주세요.",
    ),
    "health_claim": SellerQuestion(
        "질병 치료·예방이나 신체 기능 개선을 말하는 문구가 있는지 확인이 필요합니다.",
        "예: '염증 완화', '혈압 개선', '다이어트 효과'. 상세페이지에 있으면 그 문구를 그대로 적고, 없으면 '없음'이라고 적어 주세요.",
    ),
    "beauty_claim": SellerQuestion(
        "피부·모발 효과를 말하는 문구가 있는지 확인이 필요합니다.",
        "예: '미백', '주름 개선', '탈모 완화'. 상세페이지에 있으면 그 문구를 그대로 적고, 없으면 '없음'이라고 적어 주세요.",
    ),
    "ingredient": SellerQuestion(
        "제품 성분 확인이 필요합니다.",
        "예: 정제수, 글리세린, 비타민C 10%. 상세페이지나 포장의 전성분 표기를 그대로 적어 주세요.",
    ),
}

# 표시·광고: 판매자 문구가 없어 검토하지 못함 (advertising/tool.py)
NO_LISTING_QUESTION = SellerQuestion(
    "판매자가 쓴 상품 설명·홍보 문구가 없어 표시·광고를 검토하지 못했습니다. 상세페이지의 상품 설명 문구를 알려주세요.",
    "상세페이지에 적힌 제품 소개·효과·장점 문구를 그대로 붙여 넣어 주세요. 홍보 문구가 전혀 없으면 '없음'이라고 적어 주세요.",
)

# 값이 서로 달라 판단하지 않은 조건: "{표시 이름} 정보가 서로 달라 확인이 필요합니다."
CONFLICT_SUFFIX = " 정보가 서로 달라 확인이 필요합니다."
_CONFLICT_HELP = "상품명·상세 설명·속성표에 적힌 {label} 값이 서로 달라요. 실제 판매하는 상품 기준으로 어느 쪽이 맞는지 알려 주세요."

_HELP_BY_QUESTION = {item.question: item.help for item in (*QUESTIONS.values(), NO_LISTING_QUESTION)}
_FIELD_BY_QUESTION = {item.question: field for field, item in QUESTIONS.items()}

# 검증 모델 질문의 조건 필드(topic). 카탈로그 필드 + 어디에도 안 맞는 "other"
TOPIC_OTHER = "other"
TOPICS: tuple[str, ...] = (*QUESTIONS, TOPIC_OTHER)

# 재진단 답변을 상품 문구에 붙일 때 쓰는 줄 머리: "[사용자 답변] 질문 → 답변" (diagnosis/answers.py)
ANSWER_PREFIX = "[사용자 답변]"
_ANSWER_ARROW = " → "


def question_text(field: str, label: str, *, conflicted: bool = False) -> str:
    """조건 필드의 질문 문장.

    Args:
        field: 조건 필드 이름.
        label: 표시 이름 (카탈로그에 없는 필드의 기본 문장과 모순 문장에 씀).
        conflicted: 값이 서로 달라 판단하지 않은 필드인지.

    Returns:
        str: 모순이면 확인 요청 문장, 카탈로그에 있으면 그 질문, 없으면 "{표시 이름} 정보가 필요합니다.".
    """
    if conflicted:
        return f"{label}{CONFLICT_SUFFIX}"
    item = QUESTIONS.get(field)
    return item.question if item else f"{label} 정보가 필요합니다."


def field_for(question: str) -> str | None:
    """질문 문장이 어느 조건 필드의 카탈로그 질문인지 (모순 문장은 표시 이름뿐이라 못 찾음).

    Args:
        question: 질문 문장.

    Returns:
        str | None: 조건 필드. 카탈로그 질문이 아니면 None.
    """
    return _FIELD_BY_QUESTION.get(question.strip())


def answered_questions(listing_text: list[str]) -> list[str]:
    """상품 문구에 붙은 답변 줄에서 지난 회차에 물은 질문 문장을 모은다.

    Args:
        listing_text: 상품 문구. 답변 줄은 "[사용자 답변] 질문 → 답변".

    Returns:
        list[str]: 물은 질문 문장 (순서 유지).
    """
    return [line.removeprefix(ANSWER_PREFIX).split(_ANSWER_ARROW)[0].strip()
            for line in listing_text if line.startswith(ANSWER_PREFIX)]


def help_text(question: str) -> str | None:
    """질문 문장의 도움말. 카탈로그 질문과 모순 문장만 안다.

    Args:
        question: 질문 문장.

    Returns:
        str | None: 도움말. 카탈로그에 없는 문장(Tool 고유 문장·검증 모델 질문)이면 None.
    """
    help = _HELP_BY_QUESTION.get(question)
    if help is not None:
        return help
    if question.endswith(CONFLICT_SUFFIX) and question != CONFLICT_SUFFIX:
        return _CONFLICT_HELP.format(label=question.removesuffix(CONFLICT_SUFFIX))
    return None
