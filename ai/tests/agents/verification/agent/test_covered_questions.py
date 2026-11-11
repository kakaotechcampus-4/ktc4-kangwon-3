"""모델 질문 중 Tool이 이미 묻거나 판매자가 답한 조건(topic)의 질문은 뺀다. 같은 정보를 말만 바꿔 두 번 묻지 않기 위함."""

from app.agents.verification import VerificationAgent
from app.agents.verification.schemas import _Question
from app.schemas.product import Product
from app.schemas.schemas import ToolName, VerificationStatus
from app.tools.common.questions import ANSWER_PREFIX, QUESTIONS, question_text

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


def test_Tool이_모순으로_묻는_조건의_모델_질문도_뺀다(samples, stub_model):
    # 리뷰 #684: "전원 방식 정보가 서로 달라 확인이 필요합니다."와 모델의 power_source 질문이 같은 것을 두 번 묻던 문제
    conflict = question_text("power_source", "전원 방식", conflicted=True)
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [conflict])
    review = samples.review(follow_up_questions=[_question("power_source", "DC 12V와 AC 220V 중 어느 전원인가요?")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.follow_up_questions == []


def test_Tool이_전지_전용_여부를_물으면_모델의_전원_방식_질문도_뺀다(samples, stub_model):
    # #801: 얼굴 마사지기에서 전기 Tool의 battery_only 질문과 모델의 power_source 질문이 같은 회차에 같이 나옴
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [QUESTIONS["battery_only"].question])
    review = samples.review(follow_up_questions=[
        _question("power_source", "제품이 건전지나 충전지만으로만 동작하는지, 아니면 전원 코드나 어댑터를 연결하여 사용하는지 알려 주세요."),
    ])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.follow_up_questions == []


def test_Tool이_전원_방식을_물으면_모델의_전지_전용_질문도_뺀다(samples, stub_model):
    draft = _with_missing(samples.draft(), ToolName.ELECTRICAL, [QUESTIONS["power_source"].question])
    review = samples.review(follow_up_questions=[_question("battery_only", "건전지로만 쓰는 제품인가요?")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.follow_up_questions == []


def test_판매자가_지난_회차에_전지_전용_여부를_답했으면_모델의_전원_방식_질문도_뺀다(samples, stub_model):
    answered = f"{ANSWER_PREFIX} {QUESTIONS['battery_only'].question} → 배터리만"
    draft = samples.draft(Product(product_id="p1", listing_text=["얼굴 마사지기", answered]))
    review = samples.review(follow_up_questions=[_question("power_source", "어떤 전원으로 작동하나요?")])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert result.follow_up_questions == []


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
