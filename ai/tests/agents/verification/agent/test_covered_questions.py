"""모델 질문 중 Tool이 이미 묻거나 판매자가 답한 조건(topic)의 질문은 뺀다. 같은 정보를 말만 바꿔 두 번 묻지 않기 위함."""

from app.agents.verification import VerificationAgent
from app.agents.verification.schemas import _Question
from app.schemas.product import Product
from app.schemas.schemas import ToolName, VerificationStatus
from app.tools.common.questions import ANSWER_PREFIX, QUESTIONS

VOLTAGE = QUESTIONS["rated_voltage"].question


def _question(topic: str, text: str = "이 선풍기의 정격 전압을 알려 주세요.") -> _Question:
    return _Question(question=text, reason="라벨에 적힌 전압을 적어 주세요.", related_tools=[ToolName.ELECTRICAL],
                     required=True, topic=topic)


def _with_missing(draft, name: ToolName, missing: list[str]):
    for record in draft.tool_results:
        if record.tool_name is name:
            record.missing_information = missing
    return draft


def test_Tool이_이미_묻는_조건의_모델_질문은_뺀다(samples, stub_model):
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [VOLTAGE])
    review = samples.review(follow_up_questions=[_question("rated_voltage"), _question("other", "전지 용량이 표기되어 있나요?")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert [q.question for q in result.follow_up_questions] == ["전지 용량이 표기되어 있나요?"]


def test_판매자가_지난_회차에_답한_조건의_모델_질문은_답이_모름이어도_뺀다(samples, stub_model):
    draft = samples.draft(Product(product_id="p1", listing_text=["소형 선풍기", f"{ANSWER_PREFIX} {VOLTAGE} → 모르겠어요"]))
    review = samples.review(follow_up_questions=[_question("rated_voltage")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.follow_up_questions == []


def test_뺀_질문뿐이면_답변_대기_상태가_되지_않는다(samples, stub_model):
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [VOLTAGE])
    review = samples.review(follow_up_questions=[_question("rated_voltage")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.status is not VerificationStatus.USER_INPUT_REQUIRED


def test_겹치지_않는_조건의_모델_질문은_남긴다(samples, stub_model):
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [QUESTIONS["power_source"].question])
    review = samples.review(follow_up_questions=[_question("rated_voltage")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert [q.question for q in result.follow_up_questions] == ["이 선풍기의 정격 전압을 알려 주세요."]
    assert result.status is VerificationStatus.USER_INPUT_REQUIRED


def test_뺀_질문은_trace에_조건_필드로_남긴다(samples, stub_model):
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [VOLTAGE])
    review = samples.review(follow_up_questions=[_question("rated_voltage")])
    trace = []

    VerificationAgent(stub_model(review)).run(draft, trace=trace)

    [event] = [event for event in trace if event.action == "covered_questions_dropped"]
    assert "rated_voltage" in event.detail
