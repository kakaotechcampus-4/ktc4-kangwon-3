"""판단 선택 질문 목록: Tool별 질문 구성, 한 요청으로 보낼 수 있는지."""

from app.agents.decision_selection import QUESTIONS, TOOL_QUESTIONS
from app.agents.decision_selection.questions import QUESTION_LABELS, SUBJECT_NOTE
from app.clients.llm.decision import check_request
from app.schemas.clients.decision_request import DecisionRequest
from app.schemas.schemas import ToolName


def test_통관을_뺀_Tool마다_질문이_있다():
    assert set(TOOL_QUESTIONS) == set(ToolName) - {ToolName.CUSTOMS}
    assert all(TOOL_QUESTIONS.values())


def test_전체_질문은_Tool_순서대로_이어붙인_것이다():
    assert list(QUESTIONS) == [question for group in TOOL_QUESTIONS.values() for question in group]


def test_전체_질문을_한_요청으로_보낼_수_있다():
    check_request(DecisionRequest(model="typesafe/jev-latest", subject={}, questions=list(QUESTIONS)))


def test_모든_질문에_판단_대상_설명이_붙는다():
    assert all(question.instructions.startswith(SUBJECT_NOTE) for question in QUESTIONS)


def test_모든_질문에_이유용_설명이_있다():
    assert set(QUESTION_LABELS) == {question.name for question in QUESTIONS}
