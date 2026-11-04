"""진단 함수 앞 입력 가드: 볼 입력 고르기, 차단은 늦춘 일반 실패, 의심·실패는 진단 그대로."""

import logging

import pytest

from app.agents.input_guard import GuardInput, GuardOutcome, GuardVerdict
from app.diagnosis.guard import BLOCK_DELAY_SECONDS, REVIEW_FLAG_BLOCKED, guard_input, guarded
from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.domain.errors import AIResponseCode
from app.dummy.cases import CASES, DummyCaseName
from app.schemas.agent import ExtractionInput
from app.schemas.schemas import ExecutionEndReason, FollowUpQuestion
from app.schemas.session import DiagnosisInput, SessionAnswer
from app.sessions.job import JobDone, JobFailed

SOURCE = ExtractionInput(product_id="p-1", text_blocks=["무선 선풍기"], image_urls=["data:image/png;base64,AAAA"])
CONTEXT = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION)


def _previous(*texts: str):
    return CASES[DummyCaseName.KC_FAN].build("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "follow_up_questions": [FollowUpQuestion(question=text, reason="판단에 필요") for text in texts],
    })


def _answer(question_round: int, key: str, text: str) -> SessionAnswer:
    return SessionAnswer(question_round=question_round, question_key=key, answer_text=text)


class Progress:
    def __init__(self) -> None:
        self.stages: list[PipelineStage] = []

    def stage(self, stage: PipelineStage) -> None:
        self.stages.append(stage)

    def tool(self, tool_name, status) -> None:
        pass


class Job:
    """부르면 완료를 돌려주는 가짜 진단 함수."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, job_input, context, progress):
        self.calls += 1
        return JobDone(CASES[DummyCaseName.KC_FAN].build("p-1"))


def _guard(outcome: GuardOutcome, seen: list[GuardInput] | None = None):
    def guard(input: GuardInput) -> GuardVerdict:
        if seen is not None:
            seen.append(input)
        return GuardVerdict(outcome=outcome, text_score=0.9)
    return guard


def _failing_guard(input: GuardInput) -> GuardVerdict:
    raise RuntimeError("판단 서버 오류")


@pytest.fixture
def sleeps() -> list[float]:
    return []


def _run(guard, sleeps: list[float], job_input: DiagnosisInput = DiagnosisInput(source=SOURCE)):
    job, progress = Job(), Progress()
    outcome = guarded(job, guard, delay=BLOCK_DELAY_SECONDS, sleep=sleeps.append)(job_input, CONTEXT, progress)
    return outcome, job, progress


def test_첫_실행은_상품_글과_이미지를_본다():
    assert guard_input(DiagnosisInput(source=SOURCE), "p-1") == GuardInput(
        "p-1", ["무선 선풍기"], ["data:image/png;base64,AAAA"])


def test_URL만_받은_상품은_보지_않는다():
    source = ExtractionInput(product_id="p-1", source_url="https://shop.test/items/1")

    assert guard_input(DiagnosisInput(source=source), "p-1") is None


def test_재진단은_이번_회차_질문과_답변만_본다():
    job_input = DiagnosisInput(source=SOURCE, previous=_previous("정격 전압이 몇 V인가요?"),
                               answers=[_answer(1, "r1_q1", "네"), _answer(2, "r2_q1", " 5V ")])

    assert guard_input(job_input, "p-1") == GuardInput("p-1", ["질문: 정격 전압이 몇 V인가요?\n답변: 5V"])


def test_재진단에서_질문을_찾지_못하면_질문_키로_묶는다():
    job_input = DiagnosisInput(source=SOURCE, previous=_previous(), answers=[_answer(1, "r1_q3", "네")])

    assert guard_input(job_input, "p-1").texts == ["질문: r1_q3\n답변: 네"]


def test_차단이면_진단하지_않고_추출_단계_알림_뒤_늦춰_일반_오류로_실패한다(sleeps):
    outcome, job, progress = _run(_guard(GuardOutcome.BLOCK), sleeps)

    assert outcome == JobFailed(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False,
                                review_flag=REVIEW_FLAG_BLOCKED)
    assert job.calls == 0
    assert progress.stages == [PipelineStage.EXTRACTION]
    assert len(sleeps) == 1 and 5.0 <= sleeps[0] <= 10.0


@pytest.mark.parametrize("outcome", [GuardOutcome.PASS, GuardOutcome.SUSPECT])
def test_통과나_의심이면_그대로_진단한다(sleeps, outcome):
    result, job, progress = _run(_guard(outcome), sleeps)

    assert isinstance(result, JobDone)
    assert (job.calls, progress.stages, sleeps) == (1, [], [])


def test_의심이면_경고_로그에_점수와_발췌를_남긴다(sleeps, caplog):
    with caplog.at_level(logging.WARNING, logger="app.diagnosis.guard"):
        _run(_guard(GuardOutcome.SUSPECT), sleeps)

    assert "입력 확인 의심" in caplog.text
    assert "무선 선풍기" in caplog.text


def test_가드가_실패하면_그대로_진단한다(sleeps, caplog):
    with caplog.at_level(logging.WARNING, logger="app.diagnosis.guard"):
        result, job, _ = _run(_failing_guard, sleeps)

    assert isinstance(result, JobDone) and job.calls == 1
    assert "입력 확인 실패" in caplog.text


def test_볼_입력이_없으면_가드를_부르지_않는다(sleeps):
    seen: list[GuardInput] = []
    job_input = DiagnosisInput(source=ExtractionInput(product_id="p-1", source_url="https://shop.test/items/1"))

    result, job, _ = _run(_guard(GuardOutcome.BLOCK, seen), sleeps, job_input)

    assert seen == [] and job.calls == 1 and isinstance(result, JobDone)
