"""코드 규칙과 판단 답으로 6개 Tool 선택 결과를 조립. 선택 이유도 걸린 규칙·질문으로 코드가 씀."""

from collections.abc import Mapping

from ...schemas.agent import ToolSelectionItem, ToolSelectionResponse
from ...schemas.clients.decision_response import DecisionAnswer, RefusedAnswer, YesNoAnswer
from ...schemas.product import Product
from ...schemas.schemas import ToolName
from .questions import QUESTION_LABELS, TOOL_QUESTIONS
from .rules import TRUE_FIELDS, rule_reasons, unknown_wireless_fields
from .thresholds import threshold

# 원칙 2를 판단 답으로 넓힐 때 보는 질문
_ELECTRIC_QUESTION = "electric_powered"

# 이유에 값을 적는 Tool별 관련 필드 (규칙 필드 + 판단에 같이 보는 필드). 표시광고는 문구 판단이라 없음
FACT_FIELDS: dict[ToolName, tuple[str, ...]] = {
    **TRUE_FIELDS,
    ToolName.FOOD_DRUG: (*TRUE_FIELDS[ToolName.FOOD_DRUG], "skin_contact"),
    ToolName.CHILDREN: (*TRUE_FIELDS[ToolName.CHILDREN], "target_age"),
}


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
            decisions.append(_judge(tool, product, answers, threshold(model, tool)))
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
        else _item(tool, True, f"{_facts(tool, product)}열어 본 이유: 판단 모델 호출 실패로 정보 부족")
        for tool in ToolName
    ])


def _judge(tool: ToolName, product: Product, answers: Mapping[str, DecisionAnswer], limit: float) -> ToolSelectionItem:
    """Tool 질문 중 하나라도 문턱값 이상이거나 답을 거부했으면 선택한다 (모르면 선택, 원칙 1).

    이유에는 관련 필드 값과 질문별 해당 가능성만 남김. 검증 에이전트가 읽으므로 해당 여부를 단정하지 않음.

    Args:
        tool: 질문 있는 Tool.
        product: 추출된 상품 정보.
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
    facts = _facts(tool, product)
    if refused:
        labels = ", ".join(QUESTION_LABELS[name] for name in refused)
        return _item(tool, True, f"{facts}열어 본 이유: 판단 모델이 '{labels}' 답을 거부해 정보 부족")
    hits = [f"{QUESTION_LABELS[name]} {p:.2f}" for name, p in probabilities.items() if p >= limit]
    if hits:
        return _item(tool, True, (f"{facts}열어 본 이유: 판단 모델이 본 해당 가능성 {', '.join(hits)} (기준 {limit} 이상). "
                                  "실제 해당 여부는 Tool 결과 기준"))
    checked = ", ".join(f"{QUESTION_LABELS[name]} {p:.2f}" for name, p in probabilities.items())
    return _item(tool, False, f"{facts}열지 않은 이유: 판단 모델이 본 해당 가능성 {checked} 모두 기준 {limit} 미만")


def _facts(tool: ToolName, product: Product) -> str:
    """이유 앞에 붙일 관련 필드 값. 관련 필드가 없는 Tool은 빈 문자열.

    Args:
        tool: 질문 있는 Tool.
        product: 추출된 상품 정보.

    Returns:
        str: "관련 필드 a=false, b=None. " 꼴.
    """
    fields = FACT_FIELDS.get(tool, ())
    if not fields:
        return ""
    return "관련 필드 " + ", ".join(f"{field}={_value(getattr(product, field))}" for field in fields) + ". "


def _value(value: object) -> str:
    """필드 값 표기 (불리언은 소문자, 문자열은 따옴표)."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return f"'{value}'"
    return str(value)


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
    return (f"관련 필드 {'·'.join(unknown)}=None. 열어 본 이유: 판단 모델이 본 해당 가능성 "
            f"{QUESTION_LABELS[_ELECTRIC_QUESTION]} {electric:.2f} (기준 {limit} 이상)인데 무선 기능 정보 없음")


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
