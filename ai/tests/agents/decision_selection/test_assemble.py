"""판단 선택 조립: 규칙 우선, 문턱값 비교, 답 거부·누락, 판단 답으로 넓힌 원칙 2, 이유 문구."""

import pytest

from app.agents.decision_selection import QUESTIONS
from app.agents.decision_selection.assemble import assemble
from app.schemas.clients.decision_response import ChoiceAnswer, RefusedAnswer, YesNoAnswer
from app.schemas.product import Product
from app.schemas.schemas import ToolName

JEV = "typesafe/jev-latest"
# 무선 필드를 다 채워 원칙 2가 끼어들지 않는 상품
_PLAIN = {"wireless_comm": False, "wireless_charging": False, "wireless_shield": False}


def _product(**fields) -> Product:
    return Product(product_id="assemble-001", source_url=None, **fields)


def _answers(**probabilities) -> dict:
    answers = {question.name: YesNoAnswer(probability=0.05) for question in QUESTIONS}
    answers.update({name: YesNoAnswer(probability=p) for name, p in probabilities.items()})
    return answers


def _picked(result) -> dict[ToolName, tuple[bool, str]]:
    return {item.tool_name: (item.selected, item.reason) for item in result.decisions}


def test_6개_Tool을_순서대로_낸다():
    result = assemble(_product(**_PLAIN), _answers(), JEV)

    assert [item.tool_name for item in result.decisions] == list(ToolName)


def test_규칙에_걸리면_판단_답과_무관하게_선택하고_규칙을_이유로_쓴다():
    picked = _picked(assemble(_product(**_PLAIN, for_children=True), _answers(), JEV))

    assert picked[ToolName.CUSTOMS] == (True, "규칙: 해외 직구 상품은 수입 통관 대상")
    assert picked[ToolName.CHILDREN] == (True, "규칙: for_children=true")


def test_질문_하나라도_문턱값_이상이면_선택한다():
    picked = _picked(assemble(_product(**_PLAIN), _answers(children_kind=0.82, children_target=0.3), JEV))

    assert picked[ToolName.CHILDREN] == (True, "판단 모델: children_target 0.30, children_kind 0.82 (문턱 0.15)")


def test_모두_문턱값_미만이면_선택하지_않고_최고_답을_이유로_쓴다():
    picked = _picked(assemble(_product(**_PLAIN), _answers(children_kind=0.12), JEV))

    assert picked[ToolName.CHILDREN] == (False, "규칙 해당 없음. 판단 모델 최고 children_kind 0.12 < 문턱 0.15")


def test_답을_거부한_질문이_있으면_선택한다():
    answers = _answers()
    answers["ad_effect"] = RefusedAnswer()

    picked = _picked(assemble(_product(**_PLAIN), answers, JEV))

    assert picked[ToolName.LABEL_AD] == (True, "판단 모델이 답을 거부함(ad_effect). 정보 부족으로 선택")


def test_판단상_전기_제품이고_무선_정보가_없으면_전파를_선택한다():
    picked = _picked(assemble(_product(wireless_comm=False), _answers(electric_powered=0.6), JEV))

    selected, reason = picked[ToolName.RADIO]
    assert selected
    assert reason == ("판단 모델: electric_powered 0.60 (문턱 0.3)인데 wireless_charging·wireless_shield=None "
                      "(전기 제품의 무선 기능 정보 없음)")


def test_판단상_전기_제품이어도_무선_필드가_다_있으면_전파_질문으로_정한다():
    picked = _picked(assemble(_product(**_PLAIN), _answers(electric_powered=0.9), JEV))

    assert picked[ToolName.RADIO][0] is False


def test_판단상_전기_제품이_아니면_무선_정보가_없어도_전파_질문으로_정한다():
    picked = _picked(assemble(_product(), _answers(electric_powered=0.1), JEV))

    assert picked[ToolName.RADIO][0] is False


def test_문턱값은_판단_모델별로_고른다():
    picked = _picked(assemble(_product(**_PLAIN), _answers(children_kind=0.4), "openai/gpt-6-luna"))

    assert picked[ToolName.CHILDREN][0] is False


@pytest.mark.parametrize("answer", [None, ChoiceAnswer(choice="a", probabilities={"a": 1.0}, confidence=1.0)])
def test_예아니오_답이_없으면_막는다(answer):
    answers = _answers()
    if answer is None:
        del answers["children_kind"]
    else:
        answers["children_kind"] = answer

    with pytest.raises(ValueError, match="children_kind"):
        assemble(_product(**_PLAIN), answers, JEV)
