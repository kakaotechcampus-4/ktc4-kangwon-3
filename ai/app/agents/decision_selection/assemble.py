"""코드 규칙과 판단 답으로 6개 Tool 선택 결과를 조립. 선택 이유도 걸린 규칙·질문으로 코드가 씀."""

from collections.abc import Mapping

from ...schemas.agent import ToolSelectionItem, ToolSelectionResponse
from ...schemas.clients.decision_response import DecisionAnswer, RefusedAnswer, YesNoAnswer
from ...schemas.product import Product
from ...schemas.schemas import ToolName
from .questions import TOOL_QUESTIONS
from .rules import rule_reasons, unknown_wireless_fields
from .thresholds import threshold

# 원칙 2를 판단 답으로 넓힐 때 보는 질문
_ELECTRIC_QUESTION = "electric_powered"


def assemble(product: Product, answers: Mapping[str, DecisionAnswer], model: str) -> ToolSelectionResponse:
    """코드 규칙에 걸린 Tool은 선택하고, 나머지는 판단 답을 문턱값과 비교해 정한다.

    Args:
        product: 추출된 상품 정보.
        answers: 질문 이름별 판단 답. QUESTIONS 전부 있어야 함.
        model: 판단 모델 등록명 (문턱값을 고름).

    Returns:
        ToolSelectionResponse: 6개 Tool 선택 결과.

    Raises:
        ValueError: 답이 빠졌거나 예/아니오 답이 아닌 경우, 문턱값이 없는 모델인 경우.
    """
    rules = rule_reasons(product)
    decisions = []
    for tool in ToolName:
        if tool in rules:
            decisions.append(_item(tool, True, "규칙: " + ", ".join(rules[tool])))
        elif tool is ToolName.RADIO and (reason := _radio_electric_reason(product, answers, model)):
            decisions.append(_item(tool, True, reason))
        else:
            decisions.append(_judge(tool, answers, threshold(model, tool)))
    return ToolSelectionResponse(decisions=decisions)


def assemble_without_answers(product: Product) -> ToolSelectionResponse:
    """판단 답 없이 조립한다. 규칙에 안 걸린 Tool도 모두 선택 (모르면 선택, 원칙 1).

    Args:
        product: 추출된 상품 정보.

    Returns:
        ToolSelectionResponse: 6개 Tool 모두 선택한 결과.
    """
    rules = rule_reasons(product)
    return ToolSelectionResponse(decisions=[
        _item(tool, True, "규칙: " + ", ".join(rules[tool])) if tool in rules
        else _item(tool, True, "규칙 해당 없음. 판단 모델 호출 실패로 정보 부족, 선택")
        for tool in ToolName
    ])


def _judge(tool: ToolName, answers: Mapping[str, DecisionAnswer], limit: float) -> ToolSelectionItem:
    """Tool 질문 중 하나라도 문턱값 이상이거나 답을 거부했으면 선택한다 (모르면 선택, 원칙 1).

    Args:
        tool: 질문 있는 Tool.
        answers: 질문 이름별 판단 답.
        limit: 문턱값.

    Returns:
        ToolSelectionItem: 선택 여부와 이유.
    """
    probabilities = {}
    refused = []
    for question in TOOL_QUESTIONS[tool]:
        answer = _answer(answers, question.name)
        if answer is None:
            refused.append(question.name)
        else:
            probabilities[question.name] = answer
    if refused:
        return _item(tool, True, f"판단 모델이 답을 거부함({', '.join(refused)}). 정보 부족으로 선택")
    hits = [f"{name} {p:.2f}" for name, p in probabilities.items() if p >= limit]
    if hits:
        return _item(tool, True, f"판단 모델: {', '.join(hits)} (문턱 {limit})")
    top_name, top = max(probabilities.items(), key=lambda pair: pair[1])
    return _item(tool, False, f"규칙 해당 없음. 판단 모델 최고 {top_name} {top:.2f} < 문턱 {limit}")


def _radio_electric_reason(product: Product, answers: Mapping[str, DecisionAnswer], model: str) -> str | None:
    """원칙 2를 판단 답으로 넓힘: 전기 필드는 없지만 판단상 전기 제품이고 무선 필드가 None이면 전파 선택.

    Args:
        product: 추출된 상품 정보.
        answers: 질문 이름별 판단 답.
        model: 판단 모델 등록명.

    Returns:
        str | None: 선택 이유. 해당 없으면 None.
    """
    unknown = unknown_wireless_fields(product)
    if not unknown:
        return None
    electric = _answer(answers, _ELECTRIC_QUESTION)
    limit = threshold(model, ToolName.ELECTRICAL)
    if electric is None or electric < limit:
        return None
    return (f"판단 모델: {_ELECTRIC_QUESTION} {electric:.2f} (문턱 {limit})인데 "
            f"{'·'.join(unknown)}=None (전기 제품의 무선 기능 정보 없음)")


def _answer(answers: Mapping[str, DecisionAnswer], name: str) -> float | None:
    """예/아니오 답의 "예" 확률. 거부했으면 None.

    Args:
        answers: 질문 이름별 판단 답.
        name: 질문 이름.

    Returns:
        float | None: "예" 확률. 답을 거부했으면 None.

    Raises:
        ValueError: 답이 없거나 예/아니오 답이 아닌 경우.
    """
    answer = answers.get(name)
    if isinstance(answer, RefusedAnswer):
        return None
    if not isinstance(answer, YesNoAnswer):
        raise ValueError(f"판단 선택 질문 {name}의 예/아니오 답이 없습니다: {answer!r}")
    return answer.probability


def _item(tool: ToolName, selected: bool, reason: str) -> ToolSelectionItem:
    return ToolSelectionItem(tool_name=tool, selected=selected, reason=reason)
