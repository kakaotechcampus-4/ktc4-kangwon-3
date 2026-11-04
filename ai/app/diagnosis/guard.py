"""진단 함수 앞에서 입력 가드를 돌리는 곳. 첫 실행은 상품 글·이미지, 재진단은 이번 회차 질문·답변을 봄.

- 차단: 파이프라인을 부르지 않음. 추출 단계 진행 알림 → 무작위로 늦춘 뒤 일반 파이프라인 오류로 끝냄
  (가드가 있는지 드러나지 않게 보통 실패와 같은 모양). 실패 콜백 error에만 BE 전용 검토 표시를 붙임
- 의심: 진단은 그대로, 경고 로그만
- 가드 자체가 실패하면 통과로 봄 (fail-open)

URL만 받은 상품은 볼 글·이미지가 없어 건너뜀.
"""

import logging
import random
import time
from collections.abc import Callable

from ..agents.input_guard import GuardInput, GuardOutcome, GuardVerdict
from ..domain.context import ExecutionContext, PipelineStage
from ..domain.errors import AIResponseCode
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, JobFailed, Outcome, ProgressReporter
from .questions import build_questions

logger = logging.getLogger(__name__)

# 차단 때 실패를 늦추는 범위 (초)
BLOCK_DELAY_SECONDS = (8.0, 20.0)
# 차단·의심 로그에 남기는 원문 길이
EXCERPT_CHARS = 200
# 차단 실패 콜백의 BE 전용 검토 표시 값 (error.reviewFlag)
REVIEW_FLAG_BLOCKED = "r1"

# 가드 입력 → 판정. 운영은 InputGuardAgent().run
Guard = Callable[[GuardInput], GuardVerdict]


def guarded(
    job: DiagnosisJob, guard: Guard, *,
    delay: tuple[float, float] = BLOCK_DELAY_SECONDS, sleep: Callable[[float], None] = time.sleep,
) -> DiagnosisJob:
    """진단 함수 앞에 입력 가드를 붙인 진단 함수를 만든다.

    Args:
        job: 감쌀 진단 함수.
        guard: 가드 입력을 판정하는 함수.
        delay: 차단 때 실패를 늦추는 범위 (초).
        sleep: 늦추는 함수. 테스트에서 교체용.

    Returns:
        DiagnosisJob: 가드를 먼저 돌리고, 차단이 아니면 감싼 진단 함수를 부르는 진단 함수.
    """
    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        verdict = _check(guard, job_input, context.product_id)
        if verdict is None or verdict.outcome is not GuardOutcome.BLOCK:
            return job(job_input, context, progress)
        # 정상 실행처럼 추출 단계 알림 후 늦춰 실패
        progress.stage(PipelineStage.EXTRACTION)
        sleep(random.uniform(*delay))
        return JobFailed(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False, review_flag=REVIEW_FLAG_BLOCKED)

    return run


def guard_input(job_input: DiagnosisInput, product_id: str) -> GuardInput | None:
    """실행 입력에서 가드가 볼 부분을 고른다. 재진단은 원래 입력을 첫 실행에서 이미 봐 이번 회차 답변만.

    Args:
        job_input: 실행 입력.
        product_id: 상품 ID.

    Returns:
        GuardInput | None: 가드 입력. 볼 글·이미지가 없으면 None.
    """
    if job_input.previous is not None:
        texts = answer_texts(job_input)
        return GuardInput(product_id, texts) if texts else None
    source = job_input.source
    if not source.text_blocks and not source.image_urls:
        return None
    return GuardInput(product_id, list(source.text_blocks), list(source.image_urls))


def answer_texts(job_input: DiagnosisInput) -> list[str]:
    """이번 회차 답변을 질문 문장과 묶은 글 목록으로 만든다. 질문은 이전 결과에서 키를 다시 만들어 찾음.

    Args:
        job_input: 재진단 실행 입력.

    Returns:
        list[str]: "질문: ...\\n답변: ..." 글. 이전 결과나 답변이 없으면 빈 목록.
    """
    if job_input.previous is None or not job_input.answers:
        return []
    latest = max(answer.question_round for answer in job_input.answers)
    asked = {question.question_key: question.question_text
             for question in build_questions(job_input.previous, latest)}
    return [
        f"질문: {asked.get(answer.question_key, answer.question_key)}\n답변: {answer.answer_text.strip()}"
        for answer in job_input.answers
        if answer.question_round == latest
    ]


def _check(guard: Guard, job_input: DiagnosisInput, product_id: str) -> GuardVerdict | None:
    """가드를 돌리고 차단·의심이면 로그를 남긴다.

    Args:
        guard: 가드 함수.
        job_input: 실행 입력.
        product_id: 상품 ID.

    Returns:
        GuardVerdict | None: 판정. 볼 것이 없거나 가드가 실패하면 None.
    """
    input = guard_input(job_input, product_id)
    if input is None:
        return None
    try:
        verdict = guard(input)
    except Exception:
        logger.warning("입력 확인 실패, 확인 없이 진단", exc_info=True)
        return None
    if verdict.outcome is GuardOutcome.PASS:
        logger.info("입력 확인 통과 (글 %s, 이미지 %s)", verdict.text_score, verdict.image_score)
    else:
        logger.warning(
            "입력 확인 %s: 형식 %s, 글 %s, 이미지 %s, 못 본 이미지 %d, 실패 호출 %d, 발췌 %r",
            "차단" if verdict.outcome is GuardOutcome.BLOCK else "의심", verdict.format_hits, verdict.text_score,
            verdict.image_score, verdict.skipped_images, verdict.failed_calls,
            "\n".join(input.texts)[:EXCERPT_CHARS],
        )
    return verdict
