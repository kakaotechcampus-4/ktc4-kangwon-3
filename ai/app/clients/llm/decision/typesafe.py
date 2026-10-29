"""TypeSafe 판단 형식 클라이언트 (Jev, `typesafe/jev-latest`)."""

from ....schemas.clients.decision_request import (
    ChoiceQuestion,
    DecisionOption,
    DecisionQuestion,
    DecisionRequest,
    ScoreQuestion,
    YesNoQuestion,
)
from ....schemas.clients.decision_response import (
    ChoiceAnswer,
    DecisionAnswer,
    DecisionResponse,
    ScoreAnswer,
    YesNoAnswer,
)
from .base import DecisionClient


class TypeSafeDecisionClient(DecisionClient):
    """TypeSafe 판단 형식 클라이언트.

    방식 : POST/JSON
    서비스 키 : ML API 키 (Authorization: Bearer)
    비고
        판단 대상은 `state`에 객체 그대로, 질문은 이름을 키로 한 맵으로 보냄.
        예/아니오는 `noul`, 점수 단계는 설명 문자열 배열(낮은 순)이고 답은 단계 번호로 옴.
        응답 `model`에 실제 버전이 옴 (예: typesafe/jev-1.14-20261014).
    """

    def _to_payload(self, request: DecisionRequest) -> dict:
        """공통 요청을 TypeSafe 요청 본문으로 바꾼다.

        Args:
            request: 판단 요청.

        Returns:
            dict: JSON 요청 본문.
        """
        return {
            "model": request.model,
            "state": request.subject,
            "questions": {question.name: _question_payload(question) for question in request.questions},
        }

    def _from_payload(self, body: dict) -> DecisionResponse:
        """TypeSafe 응답 본문을 공통 응답으로 바꾼다.

        Args:
            body: JSON 응답 본문.

        Returns:
            DecisionResponse: 질문 이름별 답과 토큰 사용량.

        Raises:
            KeyError: 필수 필드가 빠진 경우.
            ValueError: 모르는 답 종류이거나 값이 범위를 벗어난 경우.
        """
        usage = body["usage"]
        return DecisionResponse(
            model=body["model"],
            answers={name: _answer(answer) for name, answer in body["answers"].items()},
            input_tokens=usage["input_tokens"],
            cached_tokens=usage.get("cached_prompt_tokens", 0),
            cache_write_tokens=usage.get("cache_write_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


def _question_payload(question: DecisionQuestion) -> dict:
    """질문 하나를 TypeSafe 질문으로 바꾼다."""
    if isinstance(question, YesNoQuestion):
        return {"type": "noul", "instructions": question.instructions}
    if isinstance(question, ChoiceQuestion):
        return {
            "type": "choice",
            "instructions": question.instructions,
            "criteria": {option.value: option.description for option in question.options},
        }
    if isinstance(question, ScoreQuestion):
        return {
            "type": "score",
            "instructions": question.instructions,
            "criteria": [_level_text(level) for level in question.levels],
        }
    raise TypeError(f"모르는 질문 종류: {type(question).__name__}")


def _level_text(level: DecisionOption) -> str:
    """점수 단계 하나를 TypeSafe 단계 설명으로 바꾼다. 단계마다 문자열 하나만 받아 이름과 설명을 합침."""
    return f"{level.value}: {level.description}" if level.description else level.value


def _answer(answer: dict) -> DecisionAnswer:
    """TypeSafe 답 하나를 공통 답으로 바꾼다."""
    kind = answer.get("type")
    if kind == "noul":
        return YesNoAnswer(probability=answer["noul"])
    if kind == "choice":
        return ChoiceAnswer(
            choice=answer["choice"], probabilities=answer["probabilities"], confidence=answer["confidence"],
        )
    if kind == "score":
        # 확률이 단계 번호 문자열 키로 옴 → 번호 순 리스트
        probabilities = answer["probabilities"]
        return ScoreAnswer(
            score=answer["score"],
            probabilities=[probabilities[str(index)] for index in range(len(probabilities))],
            confidence=answer["confidence"],
        )
    raise ValueError(f"모르는 TypeSafe 답 종류: {kind!r}")

