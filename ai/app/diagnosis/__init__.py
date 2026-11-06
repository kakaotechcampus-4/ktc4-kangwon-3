"""실제 진단 파이프라인을 세션 진단 함수로 잇는 곳 ([콜백 5/5] #320).

    - answers: 재진단 답변을 상품 정보에 붙임
    - assembly: 기동 때 한 번 만드는 파이프라인 부품
    - guard: 진단 함수 앞에 입력 가드를 붙임 (차단은 늦춘 일반 실패)
    - job: 파이프라인을 실행마다 조립해 돌리고 세션 결말을 정하는 진단 함수
    - questions: 파이프라인 질문 → BE 질문 (회차·순서 질문 키)
"""

from .answers import ANSWER_PREFIX, with_answers
from .assembly import PipelineParts, build_parts, build_tools
from .guard import guard_input, guarded
from .job import QuestionBuilder, build_job
from .questions import build_questions, question_key

__all__ = [
    "ANSWER_PREFIX", "PipelineParts", "QuestionBuilder", "build_job", "build_parts", "build_questions", "build_tools",
    "guard_input", "guarded", "question_key", "with_answers",
]
