"""판매자 질문 카탈로그. 질문 문장은 Tool 사이에서 같아야 하고, 도움말은 문장으로 되찾을 수 있어야 한다."""

import pytest

from app.tools.common.questions import (
    ANSWER_PREFIX,
    CONFLICT_SUFFIX,
    NO_LISTING_QUESTION,
    QUESTIONS,
    SAME_QUESTION_GROUPS,
    TOPIC_OTHER,
    TOPICS,
    answered_questions,
    field_for,
    help_text,
    question_text,
    same_question_fields,
)


def test_카탈로그_질문_문장은_서로_다르다():
    # 진단 단계가 문장으로 질문을 합치므로 다른 조건이 같은 문장을 쓰면 답이 섞인다
    texts = [item.question for item in QUESTIONS.values()] + [NO_LISTING_QUESTION.question]
    assert len(texts) == len(set(texts))


@pytest.mark.parametrize("field", sorted(QUESTIONS))
def test_카탈로그_질문은_확인할_것과_답하는_법을_모두_담는다(field):
    item = QUESTIONS[field]
    assert item.question.strip() and item.help.strip()
    # 질문은 항목 이름만 적지 않고(테스트 피드백), 도움말은 답하는 법으로 맺는다
    assert not item.question.endswith("정보가 필요합니다.")
    assert item.help.endswith("주세요.")


def test_카탈로그에_있는_필드는_그_질문_문장을_쓴다():
    assert question_text("rated_voltage", "정격 전압") == "제품의 정격 전압 확인이 필요합니다."


def test_카탈로그에_없는_필드는_표시_이름으로_기본_문장을_만든다():
    assert question_text("serial_number", "일련번호") == "일련번호 정보가 필요합니다."


def test_값이_서로_다른_필드는_카탈로그와_상관없이_확인_요청_문장이다():
    assert question_text("rated_voltage", "정격 전압", conflicted=True) == "정격 전압 정보가 서로 달라 확인이 필요합니다."


def test_카탈로그_질문_문장으로_도움말을_되찾는다():
    assert help_text("제품에 어떤 기능이 있는지 확인이 필요합니다.") == QUESTIONS["function"].help
    assert help_text(NO_LISTING_QUESTION.question) == NO_LISTING_QUESTION.help


def test_모순_문장의_도움말은_표시_이름을_넣어_만든다():
    assert help_text(f"정격 전압{CONFLICT_SUFFIX}") == (
        "상품명, 상세 설명, 속성표에 적힌 정격 전압 값이 서로 달라요. 실제 판매하는 상품 기준으로 어느 쪽이 맞는지 알려 주세요."
    )


@pytest.mark.parametrize("question", ["기능을 알려 주세요.", "제외 물품 해당 여부 정보가 필요합니다.", CONFLICT_SUFFIX, ""])
def test_카탈로그에_없는_문장은_도움말이_없다(question):
    assert help_text(question) is None


def test_검증_질문_topic은_카탈로그_필드와_other다():
    assert TOPICS == (*QUESTIONS, TOPIC_OTHER)


def test_같은_내용을_묻는_조건은_한_묶음이다():
    # #801: 전지로만 동작하는지는 전원 방식의 한 갈래라 어느 쪽을 물었든 전원 질문은 한 번만 나와야 한다
    assert same_question_fields("power_source") == {"power_source", "battery_only"}
    assert same_question_fields("battery_only") == {"power_source", "battery_only"}


def test_묶음이_없는_조건은_자기_자신만이다():
    assert same_question_fields("rated_voltage") == {"rated_voltage"}
    assert same_question_fields(TOPIC_OTHER) == {TOPIC_OTHER}


def test_묶음의_조건은_모두_카탈로그에_있다():
    for group in SAME_QUESTION_GROUPS:
        assert len(group) >= 2
        assert group <= set(QUESTIONS)


def test_카탈로그_질문_문장으로_조건_필드를_되찾는다():
    assert field_for("제품의 정격 전압 확인이 필요합니다.") == "rated_voltage"
    assert field_for(" 제품의 정격 전압 확인이 필요합니다. ") == "rated_voltage"


@pytest.mark.parametrize("question", ["기능을 알려 주세요.", f"일련번호{CONFLICT_SUFFIX}", NO_LISTING_QUESTION.question, ""])
def test_카탈로그_질문도_아는_모순_문장도_아니면_조건_필드가_없다(question):
    assert field_for(question) is None


def test_모순_문장은_표시_이름으로_조건_필드를_되찾는다():
    # 리뷰 #684: Tool이 모순으로 전원 방식을 물으면 검증 모델의 power_source 질문도 빠져야 한다
    assert field_for(question_text("power_source", "전원 방식", conflicted=True)) == "power_source"
    assert field_for(question_text("intended_use", "제품 용도", conflicted=True)) == "intended_use"


def test_Tool의_표시_이름은_모두_카탈로그_labels에_있다():
    # 표시 이름이 어긋나면 모순 문장에서 필드를 못 찾아 중복 제거가 조용히 빠진다
    import importlib
    from app.tools.base.evidence_search import EvidenceSearchTool
    missing = []
    for name in ("customs", "electrical", "radio", "children", "food_drug"):
        module = importlib.import_module(f"app.tools.{name}.tool")
        tool = next(obj for obj in vars(module).values()
                    if isinstance(obj, type) and issubclass(obj, EvidenceSearchTool) and obj is not EvidenceSearchTool)
        for field, label in tool.field_labels.items():
            if label not in QUESTIONS[field].labels:
                missing.append((name, field, label))
    assert missing == []


def test_가운뎃점을_쓰지_않는다():
    for item in (*QUESTIONS.values(), NO_LISTING_QUESTION):
        assert "·" not in item.question and "·" not in item.help


def test_답변_줄에서_지난_회차_질문_문장을_모은다():
    listing = ["소형 선풍기", f"{ANSWER_PREFIX} 제품의 정격 전압 확인이 필요합니다. → 모르겠어요",
               f"{ANSWER_PREFIX} r1_q2 → 220V", "정격 전압 → 220V"]

    assert answered_questions(listing) == ["제품의 정격 전압 확인이 필요합니다.", "r1_q2"]
