"""재진단 답변을 상품 정보에 붙이는 규칙을 검증한다."""

from app.diagnosis.answers import with_answers
from app.dummy.cases import CASES, DummyCaseName
from app.schemas.agent import ExtractionInput
from app.schemas.product import Product
from app.schemas.schemas import ExecutionEndReason, FollowUpQuestion
from app.schemas.session import DiagnosisInput, SessionAnswer

SOURCE = ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"])
PRODUCT = Product(product_id="p-1", listing_text=["무선 선풍기", "USB 충전"])


def _previous(*texts: str):
    return CASES[DummyCaseName.KC_FAN].build("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "follow_up_questions": [FollowUpQuestion(question=text, reason="판단에 필요") for text in texts],
    })


def _answer(question_round: int, key: str, text: str) -> SessionAnswer:
    return SessionAnswer(question_round=question_round, question_key=key, answer_text=text)


def test_첫_실행은_상품_정보를_그대로_돌려준다():
    assert with_answers(PRODUCT, DiagnosisInput(source=SOURCE)) is PRODUCT


def test_재진단은_질문과_답변을_표시한_줄로_판매자_문구_끝에_붙인다():
    job_input = DiagnosisInput(source=SOURCE, previous=_previous("배터리로만 동작하나요?", "정격 전압이 몇 V인가요?"),
                               answers=[_answer(1, "r1_q1", " 네, 배터리 전용이에요 "), _answer(1, "r1_q2", "5V")])

    product = with_answers(PRODUCT, job_input)

    assert product.listing_text == [
        "무선 선풍기", "USB 충전",
        "[사용자 답변] 배터리로만 동작하나요? → 네, 배터리 전용이에요",
        "[사용자 답변] 정격 전압이 몇 V인가요? → 5V",
    ]
    assert PRODUCT.listing_text == ["무선 선풍기", "USB 충전"]


def test_2회차는_이번_회차_답변만_붙인다():
    # 1회차 답변 줄은 이전 결과의 상품 정보에 이미 있음
    carried = PRODUCT.model_copy(update={"listing_text": [*PRODUCT.listing_text, "[사용자 답변] 배터리로만 동작하나요? → 네"]})
    job_input = DiagnosisInput(source=SOURCE, previous=_previous("정격 전압이 몇 V인가요?"),
                               answers=[_answer(1, "r1_q1", "네"), _answer(2, "r2_q1", "5V")])

    product = with_answers(carried, job_input)

    assert product.listing_text[-2:] == ["[사용자 답변] 배터리로만 동작하나요? → 네", "[사용자 답변] 정격 전압이 몇 V인가요? → 5V"]


def test_질문을_찾지_못하면_질문_키로_붙인다():
    job_input = DiagnosisInput(source=SOURCE, previous=_previous(), answers=[_answer(1, "r1_q3", "네")])

    assert with_answers(PRODUCT, job_input).listing_text[-1] == "[사용자 답변] r1_q3 → 네"
