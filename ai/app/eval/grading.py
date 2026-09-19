"""필드 하나를 채점하는 규칙.

LLM을 부르지 않는 순수 함수만 둔다. 채점 기준 자체가 틀리면 측정값 전부가
무의미해지므로, 이 모듈은 결정적 단위 테스트로 검증한다(test_eval_grading.py).

등급은 오답을 같은 무게로 세지 않는다. 규제 판정에서 "없음을 확인"(false)과
"모르겠음"(null)의 위험이 전혀 다르기 때문이다. 자세한 근거는
docs/EXTRACTION_EVAL.md 1절.
"""

from enum import StrEnum
from typing import Any


class Grade(StrEnum):
    """한 필드 한 번 실행의 채점 결과."""

    OK = "ok"
    # 규제 판정을 조용히 틀리게 만든다. 있는 것을 없다고 확정하거나,
    # 근거가 없는데 확정한 경우.
    C1 = "c1"
    # 안전한 실패. null로 넘겨서 하위 단계가 "확인 필요"로 처리할 수 있다.
    C2 = "c2"
    # 비용만 드는 실패. 불필요한 툴이 실행되지만 판단은 틀리지 않는다.
    C3 = "c3"


class Stability(StrEnum):
    """같은 입력을 N회 돌렸을 때 한 필드의 거동."""

    STABLE_OK = "stable_ok"
    # N회 모두 같은 오답. 프롬프트·스키마로 고칠 수 있는 체계적 오류다.
    # 몇 번을 돌려도 같은 답이 나와서 정답표 없이는 발견되지 않는다.
    STABLE_WRONG = "stable_wrong"
    # 런마다 값이 갈린다. 모델에 근거가 없다는 신호.
    UNSTABLE = "unstable"


# 3-state boolean 채점표. (정답, 예측) -> 등급.
# null 정답에 확정을 답하면 C1인 이유: 페이지에 근거가 없는데 하위 단계가
# 그 확정을 신뢰하게 된다.
_BOOLEAN_GRADES: dict[tuple[bool | None, bool | None], Grade] = {
    (True, True): Grade.OK,
    (True, False): Grade.C1,
    (True, None): Grade.C2,
    (False, True): Grade.C3,
    (False, False): Grade.OK,
    (False, None): Grade.C2,
    (None, True): Grade.C1,
    (None, False): Grade.C1,
    (None, None): Grade.OK,
}


def _is_blank(value: str | None) -> bool:
    """값이 없는 것으로 볼지 판단한다.

    스키마(ProductAttributes)가 빈 문자열을 None으로 바꿔주지만, 정답표나 테스트가
    ""를 직접 넣는 경로는 그 validator를 거치지 않는다. 채점기에서도 한 번 더 막는다.
    """
    return not (value or "").strip()


def grade_boolean(truth: bool | None, predicted: bool | None) -> Grade:
    """3-state boolean 필드를 채점한다."""
    try:
        return _BOOLEAN_GRADES[(truth, predicted)]
    except KeyError as exc:  # bool도 None도 아닌 값이 들어온 경우
        raise ValueError(f"boolean 필드에 올 수 없는 값입니다: truth={truth!r} predicted={predicted!r}") from exc


def grade_verbatim(truth: str | None, predicted: str | None) -> Grade:
    """원문을 보존해야 하는 텍스트 필드(target_age)를 채점한다.

    정답 문자열이 예측 안에 그대로 들어 있어야 한다. "만 14세 이상"을 "14세"로
    줄이면 어린이제품 판정 근거가 사라지므로 오답으로 본다.
    """
    if truth is None:
        # 근거가 없는데 값을 지어냈으면 치명, 비워뒀으면 정답.
        return Grade.OK if _is_blank(predicted) else Grade.C1
    if _is_blank(predicted):
        return Grade.C2
    return Grade.OK if truth in predicted else Grade.C1


def grade_keywords(
    required: list[str] | None, allowed: list[str] | None, predicted: str | None
) -> Grade:
    """표현이 흔들려도 되는 텍스트 필드를 채점한다.

    required: 예측에 이 단어들이 모두 들어 있어야 한다.
    allowed: 예측이 이 목록 중 하나와 같아야 한다(동의어 목록).
    둘 다 비어 있으면 채점하지 않고 OK로 둔다.
    """
    if not required and not allowed:
        return Grade.OK
    if _is_blank(predicted):
        return Grade.C2
    normalized = predicted.strip().lower()
    if allowed:
        return Grade.OK if normalized in {a.strip().lower() for a in allowed} else Grade.C1
    return Grade.OK if all(word.lower() in normalized for word in (required or [])) else Grade.C1


def attribute_tokens(attributes: list[dict]) -> set[str]:
    """속성 목록에서 값 토큰만 모은다.

    모델이 "CE-RoHS; CE-EMC(Electric)"처럼 한 항목에 여러 값을 이어 쓰므로
    ";"와 ","로 쪼갠다. 괄호 설명이 붙은 토큰은 괄호 앞부분도 함께 넣는다.
    """
    tokens: set[str] = set()
    for attribute in attributes:
        for piece in str(attribute.get("value", "")).replace(",", ";").split(";"):
            token = piece.strip().lower()
            if not token:
                continue
            tokens.add(token)
            head, sep, _ = token.partition("(")
            if sep:
                tokens.add(head.strip())
    return tokens


def grade_attribute_value(wanted: str, attributes: list[dict]) -> Grade:
    """어떤 사실이 attributes에 담겼는지 본다. 항목 이름은 보지 않는다.

    같은 사실을 "용량"으로도 "배터리 용량"으로도 적는 것이 실측으로 확인됐다.
    이름이 다르다는 이유로 "놓쳤다"고 세면 사실 포착 여부가 아니라 라벨 표현을
    재게 된다. 이름의 흔들림은 별도로 보고한다(attribute_names).
    """
    return Grade.OK if wanted.strip().lower() in attribute_tokens(attributes) else Grade.C2


def attribute_names_for(wanted: str, attributes: list[dict]) -> list[str]:
    """그 값을 담은 항목의 이름들. 런마다 이름이 갈리는지 보려고 쓴다."""
    target = wanted.strip().lower()
    return sorted(
        {
            str(a.get("name", ""))
            for a in attributes
            if target in attribute_tokens([a])
        }
    )


def grade_required_items(required: list[Any], present: list[Any]) -> list[Grade]:
    """정답표가 요구한 항목이 결과에 있는지 하나씩 채점한다.

    놓친 항목은 C2다. 값을 지어낸 경우는 forbidden 쪽에서 따로 본다.
    """
    present_set = {_freeze(item) for item in present}
    return [Grade.OK if _freeze(item) in present_set else Grade.C2 for item in required]


def grade_forbidden_items(forbidden: list[Any], present: list[Any]) -> list[Grade]:
    """페이지에 없는데 결과에 들어온 항목을 채점한다. 지어낸 값이므로 C1이다."""
    present_set = {_freeze(item) for item in present}
    return [Grade.C1 if _freeze(item) in present_set else Grade.OK for item in forbidden]


def classify_stability(grades: list[Grade], values: list[Any]) -> Stability:
    """N회 실행의 등급·값을 보고 필드의 거동을 분류한다.

    값이 갈리면 등급이 우연히 같아도 UNSTABLE이다. 예측이 True와 False를
    오가는데 정답이 None이라 둘 다 C1인 경우가 실제로 있어서, 등급만 보면
    "안정적으로 틀린다"로 잘못 읽힌다.
    """
    if not grades:
        raise ValueError("실행 결과가 없습니다.")
    if any(v != values[0] for v in values):
        return Stability.UNSTABLE
    return Stability.STABLE_OK if grades[0] is Grade.OK else Stability.STABLE_WRONG


def is_hard_flip(values: list[Any]) -> bool:
    """확정끼리 진동했는지 본다(True <-> False).

    확정 <-> null 진동보다 심각하다. 후자는 "확신이 없다"는 신호라도 남지만,
    전자는 정반대 확정을 번갈아 주장하는 것이다.
    """
    seen = {v for v in values}
    return True in seen and False in seen


def _freeze(item: Any) -> Any:
    """dict를 집합에 넣을 수 있게 정렬된 튜플로 바꾼다."""
    if isinstance(item, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in item.items()))
    if isinstance(item, list):
        return tuple(_freeze(v) for v in item)
    return item
