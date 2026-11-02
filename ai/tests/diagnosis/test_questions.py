"""파이프라인 질문 → BE 질문 변환을 검증한다."""

from app.diagnosis.questions import build_questions
from app.dummy.cases import CASES, DummyCaseName
from app.schemas.schemas import ExecutionEndReason, FollowUpQuestion, ToolName


def _result(*questions: FollowUpQuestion):
    return CASES[DummyCaseName.KC_FAN].build("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED, "follow_up_questions": list(questions)})


def _question(text: str, *, required: bool = True, reason: str = "판단에 필요") -> FollowUpQuestion:
    return FollowUpQuestion(question=text, reason=reason, related_tools=[ToolName.ELECTRICAL], required=required)


def test_질문_키는_회차와_순서로_만들고_꼭_필요한_질문을_앞에_둔다():
    questions = build_questions(_result(
        _question("사용 연령이 몇 세인가요?", required=False),
        _question("배터리로만 동작하나요?", reason="배터리 전용이면 안전인증 대상에서 빠질 수 있음"),
    ), question_round=1)

    assert [(q.question_key, q.question_order, q.question_text) for q in questions] == [
        ("r1_q1", 1, "배터리로만 동작하나요?"),
        ("r1_q2", 2, "사용 연령이 몇 세인가요?"),
    ]
    assert questions[0].help_text == "배터리 전용이면 안전인증 대상에서 빠질 수 있음"


def test_2회차_질문_키는_1회차_키와_겹치지_않는다():
    first = build_questions(_result(_question("배터리로만 동작하나요?")), question_round=1)
    second = build_questions(_result(_question("정격 전압이 몇 V인가요?")), question_round=2)

    assert {q.question_key for q in first}.isdisjoint(q.question_key for q in second)
    assert second[0].question_key == "r2_q1"


def test_같은_문장은_한_번만_묻고_빈_문장은_뺀다():
    questions = build_questions(_result(
        _question("배터리로만 동작하나요?"), _question(" 배터리로만 동작하나요? "), _question("  "),
    ), question_round=1)

    assert [q.question_text for q in questions] == ["배터리로만 동작하나요?"]


def test_이유가_비어_있으면_도움말은_없다():
    assert build_questions(_result(_question("배터리로만 동작하나요?", reason=" ")), 1)[0].help_text is None
