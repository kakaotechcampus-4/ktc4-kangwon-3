"""파이프라인 질문(FollowUpQuestion)을 BE에 보낼 질문(PublicQuestionDto)으로 바꾼다.

질문 키는 회차와 순서로 만듦 (r1_q1). 회차가 들어가서 2회차에 지난 회차 키를 다시 쓰지 않음 (#310).
필드별 고정 키(target_age 등)는 답변 구조화(#412)에서 정함.
"""

from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import FinalAssessment


def question_key(question_round: int, order: int) -> str:
    """질문 키. 재진단 답변이 어느 질문의 답인지 이 키로 맞춤.

    Args:
        question_round: 질문 회차 (1부터).
        order: 회차 안 질문 순서 (1부터).

    Returns:
        str: "r{회차}_q{순서}".
    """
    return f"r{question_round}_q{order}"


def build_questions(result: FinalAssessment, question_round: int) -> list[PublicQuestionDto]:
    """답변이 필요한 결과의 질문을 BE 질문으로 바꾼다. 꼭 필요한 질문을 앞에 둠.

    Args:
        result: 종료 사유가 user_input_required인 결과.
        question_round: 이번 질문 회차 (1부터).

    Returns:
        list[PublicQuestionDto]: 질문 키·순서·문장·도움말. 결과에 질문이 없으면 빈 목록.
    """
    # 같은 문장은 한 번만 (검증 병합에서도 문장으로 합침), 빈 문장은 뺌
    unique = list({question.question.strip(): question for question in result.follow_up_questions
                   if question.question.strip()}.values())
    ordered = sorted(unique, key=lambda question: not question.required)
    return [
        PublicQuestionDto(
            question_key=question_key(question_round, order),
            question_order=order,
            question_text=question.question.strip(),
            # 왜 묻는지 (FE가 질문 아래 도움말로 보여 줌)
            help_text=question.reason.strip() or None,
        )
        for order, question in enumerate(ordered, start=1)
    ]
