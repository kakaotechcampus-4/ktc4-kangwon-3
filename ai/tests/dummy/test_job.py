"""시나리오 더미 진단 함수가 흐름별로 질문·실패·완료를, 결과 종류별로 공개 진단서 상태를 맞게 내는지 확인한다."""

import pytest

from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.dummy import DummyFlow, DummyResult, DummyScenario, job, mark_scenario, run_scenario_diagnosis
from app.routers._dummy import DummyAssessmentPresenter
from app.schemas.agent import ExtractionInput
from app.schemas.session import DiagnosisInput, SessionAnswer
from app.sessions.job import JobDone, JobFailed, JobNeedsInput


class _Recorder:
    def __init__(self) -> None:
        self.stages: list[PipelineStage] = []

    def stage(self, stage: PipelineStage) -> None:
        self.stages.append(stage)

    def tool(self, tool_name, status) -> None:
        raise AssertionError("더미는 Tool 진행을 보내지 않음")


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch):
    monkeypatch.setattr(job, "STAGE_SECONDS", 0)


def _run(flow: DummyFlow, result: DummyResult = DummyResult.CERTIFICATION, answered_rounds: int = 0):
    source = mark_scenario(ExtractionInput(product_id="p-1"), DummyScenario(flow=flow, result=result))
    answers = [
        SessionAnswer(question_round=round_, question_key=f"k{round_}", answer_text="네")
        for round_ in range(1, answered_rounds + 1)
    ]
    recorder = _Recorder()
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.DUMMY)
    outcome = run_scenario_diagnosis(DiagnosisInput(source=source, answers=answers), context, recorder)
    return outcome, recorder.stages


@pytest.mark.parametrize(("flow", "answered_rounds", "expected"), [
    (DummyFlow.NONE, 0, JobDone),
    (DummyFlow.ONE_ROUND, 0, JobNeedsInput),
    (DummyFlow.ONE_ROUND, 1, JobDone),
    (DummyFlow.TWO_ROUNDS, 0, JobNeedsInput),
    (DummyFlow.TWO_ROUNDS, 1, JobNeedsInput),
    (DummyFlow.TWO_ROUNDS, 2, JobDone),
    (DummyFlow.FAILED, 0, JobFailed),
    (DummyFlow.FAILED_AFTER_ANSWER, 0, JobNeedsInput),
    (DummyFlow.FAILED_AFTER_ANSWER, 1, JobFailed),
])
def test_흐름과_답한_회차로_결말을_정한다(flow, answered_rounds, expected):
    outcome, stages = _run(flow, answered_rounds=answered_rounds)

    assert type(outcome) is expected
    # 완료만 모든 단계, 질문·실패는 Tool 실행 전에 멈춤
    assert len(stages) == (6 if expected is JobDone else 2)


def test_2회차_질문은_1회차와_키가_겹치지_않는다():
    first, _ = _run(DummyFlow.TWO_ROUNDS)
    second, _ = _run(DummyFlow.TWO_ROUNDS, answered_rounds=1)

    first_keys = {question.question_key for question in first.questions}
    second_keys = {question.question_key for question in second.questions}
    assert first_keys and second_keys and not first_keys & second_keys


def test_실패는_재시도_불가_파이프라인_오류다():
    outcome, _ = _run(DummyFlow.FAILED)

    assert (outcome.error_code, outcome.retryable) == ("AI_PIPELINE_ERROR", False)


@pytest.mark.parametrize(("result", "expected"), [
    (DummyResult.ALLOWED, ("completed", "PURCHASING_AGENT_ALLOWED")),
    (DummyResult.CERTIFICATION, ("completed", "DIRECT_IMPORT_CERTIFICATION_REQUIRED")),
    (DummyResult.RECHECK, ("incomplete", "RECHECK_REQUIRED")),
])
def test_결과_종류마다_공개_진단서_상태가_다르다(result, expected):
    outcome, _ = _run(DummyFlow.NONE, result)

    assessment = DummyAssessmentPresenter().assessment(outcome.result)

    assert (assessment.status, assessment.result_status) == expected


def test_대행_구매_가능_결과는_인증_분야를_건너뛴다():
    outcome, _ = _run(DummyFlow.NONE, DummyResult.ALLOWED)

    assessment = DummyAssessmentPresenter().assessment(outcome.result)

    cards = {review.tool_name: review.status for review in assessment.tool_reviews}
    assert cards["RADIO"] == cards["ELECTRICAL"] == cards["CHILDREN"] == "SKIPPED"


def test_재진단_결과_요약에_받은_답변을_붙인다():
    source = mark_scenario(
        ExtractionInput(product_id="p-1"), DummyScenario(flow=DummyFlow.ONE_ROUND, result=DummyResult.CERTIFICATION),
    )
    answers = [SessionAnswer(question_round=1, question_key="battery_only", answer_text="아니요, 어댑터도 씀")]
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.DUMMY)

    outcome = run_scenario_diagnosis(DiagnosisInput(source=source, answers=answers), context, _Recorder())

    assert "내장 배터리로만 동작하나요? → 아니요, 어댑터도 씀" in outcome.result.summary


def test_답변이_없으면_요약을_바꾸지_않는다():
    outcome, _ = _run(DummyFlow.NONE)

    assert "받은 답변" not in outcome.result.summary
