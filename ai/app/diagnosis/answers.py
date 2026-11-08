"""재진단 답변을 상품 정보에 붙인다. 답변 구조화(#412) 전까지 쓰는 방식.

답변은 판매자 문구(listing_text) 끝에 "[사용자 답변] 질문 → 답변" 줄로 붙임. 판매자 원문과 구분되게 표시만 하고,
Tool·검증은 이 줄을 다른 문구와 같이 읽음.
붙인 상품이 이번 실행 결과(result.product)로 남으므로, 다음 회차에는 이번 회차 답변만 붙이면 됨.
"""

from ..schemas.product import Product
from ..schemas.session import DiagnosisInput
from ..tools.common.questions import ANSWER_PREFIX
from .questions import build_questions

__all__ = ["ANSWER_PREFIX", "with_answers"]


def with_answers(product: Product, job_input: DiagnosisInput) -> Product:
    """마지막 회차 답변을 상품 정보에 붙인 복사본을 만든다. 첫 실행이면 그대로 돌려줌.

    질문 문장은 이전 결과에서 같은 규칙으로 질문 키를 다시 만들어 찾음 (질문은 이전 결과에만 있음).

    Args:
        product: 추출 단계가 돌려준 상품 정보. 재진단이면 이전 실행의 상품 정보.
        job_input: 실행 입력.

    Returns:
        Product: 답변 줄을 붙인 복사본. 붙일 답변이 없으면 받은 상품 정보.
    """
    previous = job_input.previous
    if previous is None or not job_input.answers:
        return product
    latest = max(answer.question_round for answer in job_input.answers)
    asked = {question.question_key: question.question_text for question in build_questions(previous, latest)}
    lines = [
        # 질문을 못 찾으면 키만 (답변 검사는 세션이 이미 함)
        f"{ANSWER_PREFIX} {asked.get(answer.question_key, answer.question_key)} → {answer.answer_text.strip()}"
        for answer in job_input.answers
        if answer.question_round == latest
    ]
    return product.model_copy(update={"listing_text": [*product.listing_text, *lines]})
