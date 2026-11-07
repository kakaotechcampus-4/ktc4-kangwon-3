"""진단 단계 어댑터: 추출은 실행 입력 전체로 부르고 이번 회차 답변을 붙인다."""

from app.diagnosis.stages import JobInputExtraction
from app.dummy.cases import CASES, DummyCaseName
from app.schemas.agent import ExtractionInput
from app.schemas.product import Product
from app.schemas.schemas import FollowUpQuestion
from app.schemas.session import DiagnosisInput, SessionAnswer

SOURCE = ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"])


class _Step:
    def __init__(self):
        self.received = []

    def run(self, job_input):
        self.received.append(job_input)
        return Product(product_id="p-1", listing_text=["무선 선풍기"])


def test_추출은_원래_입력이_아니라_실행_입력_전체로_부르고_첫_실행이면_그대로_돌려준다():
    step = _Step()
    job_input = DiagnosisInput(source=SOURCE)

    product = JobInputExtraction(step, job_input).run(SOURCE)

    assert step.received == [job_input]
    assert product.listing_text == ["무선 선풍기"]


def test_재진단은_추출_결과에_이번_회차_답변을_붙인다():
    previous = CASES[DummyCaseName.KC_FAN].build("p-1").model_copy(update={"follow_up_questions": [
        FollowUpQuestion(question="배터리로만 동작하나요?", reason="판단에 필요")]})
    job_input = DiagnosisInput(source=SOURCE, previous=previous, answers=[
        SessionAnswer(question_round=1, question_key="r1_q1", answer_text="네")])

    product = JobInputExtraction(_Step(), job_input).run(SOURCE)

    assert product.listing_text == ["무선 선풍기", "[사용자 답변] 배터리로만 동작하나요? → 네"]
