"""케이스 더미 진단 함수가 케이스별로 질문·실패·완료를 내고, 케이스들이 화면 경우를 골고루 덮는지 확인한다."""

import pytest

from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.dummy import CASES, DummyCaseName, job, mark_case, run_scenario_diagnosis
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


def _run(case: DummyCaseName, answers: list[SessionAnswer] | None = None):
    source = mark_case(ExtractionInput(product_id="p-1"), case)
    recorder = _Recorder()
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.DUMMY)
    outcome = run_scenario_diagnosis(DiagnosisInput(source=source, answers=answers or []), context, recorder)
    return outcome, recorder.stages


def _play(case: DummyCaseName):
    """질문에 모두 '네'로 답하며 끝까지 돌려 회차별 질문과 마지막 결말을 돌려준다."""
    answers, asked = [], []
    outcome, _ = _run(case)
    while isinstance(outcome, JobNeedsInput):
        asked.append(outcome.questions)
        answers += [
            SessionAnswer(question_round=len(asked), question_key=question.question_key, answer_text="네")
            for question in outcome.questions
        ]
        outcome, _ = _run(case, answers)
    return asked, outcome


def _assessment(case: DummyCaseName):
    return DummyAssessmentPresenter().assessment(CASES[case].build("p-1"))


@pytest.mark.parametrize("case", list(DummyCaseName))
def test_케이스의_질문을_다_답하면_완료하거나_실패한다(case):
    asked, outcome = _play(case)

    assert len(asked) == len(CASES[case].rounds)
    assert type(outcome) is (JobFailed if CASES[case].fails else JobDone)


@pytest.mark.parametrize("case", list(DummyCaseName))
def test_질문은_회차마다_새_키이고_회차_안에서_순서가_겹치지_않는다(case):
    rounds = CASES[case].rounds
    keys = [question.question_key for questions in rounds for question in questions]

    assert len(keys) == len(set(keys))
    for questions in rounds:
        assert sorted(question.question_order for question in questions) == list(range(1, len(questions) + 1))


@pytest.mark.parametrize("case", [case for case in DummyCaseName if not CASES[case].fails])
def test_완료_케이스는_콜백_검사를_통과하는_공개_진단서가_된다(case):
    assessment = _assessment(case)

    assert {review.tool_name for review in assessment.tool_reviews} == {
        "CUSTOMS", "CHILDREN", "ELECTRICAL", "RADIO", "FOOD_DRUG", "LABEL_AD",
    }


def test_케이스들이_질문_회차_선택_Tool_수_분야_카드_결과_상태를_골고루_덮는다():
    done = [case for case in DummyCaseName if not CASES[case].fails]
    assessments = [_assessment(case) for case in done]

    assert {len(CASES[case].rounds) for case in DummyCaseName} == {0, 1, 2, 3}
    assert {min(len(CASES[case].build("p-1").selected_tools), 2) for case in done} == {0, 1, 2}
    assert {review.status for a in assessments for review in a.tool_reviews} == {"COMPLETED", "SKIPPED", "INCOMPLETE"}
    assert {a.result_status for a in assessments} == {
        "PURCHASING_AGENT_ALLOWED", "DIRECT_IMPORT_CERTIFICATION_REQUIRED", "RECHECK_REQUIRED",
    }
    assert {CASES[case].rounds != [] for case in DummyCaseName if CASES[case].fails} == {True, False}


def test_질문·실패는_Tool_실행_전에_멈추고_완료만_모든_단계를_지난다():
    _, asked_stages = _run(DummyCaseName.POWER_BANK)
    _, failed_stages = _run(DummyCaseName.FAILED)
    _, done_stages = _run(DummyCaseName.KC_FAN)

    assert (len(asked_stages), len(failed_stages), len(done_stages)) == (2, 2, 6)


def test_실패는_재시도_불가_파이프라인_오류다():
    outcome, _ = _run(DummyCaseName.FAILED)

    assert (outcome.error_code, outcome.retryable) == ("AI_PIPELINE_ERROR", False)


def test_재진단_결과_요약에_받은_답변을_붙인다():
    answers = [SessionAnswer(question_round=1, question_key="rated_wh", answer_text="37Wh")]

    outcome, _ = _run(DummyCaseName.POWER_BANK, answers)

    assert "배터리 정격 용량(Wh)이 표기돼 있나요? → 37Wh" in outcome.result.summary


def test_답변이_없으면_요약을_바꾸지_않는다():
    outcome, _ = _run(DummyCaseName.KC_FAN)

    assert "받은 답변" not in outcome.result.summary
