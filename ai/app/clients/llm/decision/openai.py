"""OpenAI 판단 형식 클라이언트 (Luna, `openai/gpt-6-luna`)."""

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
    DecisionUsage,
    RefusedAnswer,
    ScoreAnswer,
    YesNoAnswer,
)
from .base import DecisionClient


class OpenAIDecisionClient(DecisionClient):
    """OpenAI 판단 형식 클라이언트.

    방식 : POST/JSON
    서비스 키 : ML API 키 (Authorization: Bearer)
    비고
        `input`은 문자열·메시지 배열만 받아 판단 대상 객체는 `input_json` 파트로 보냄 (객체 그대로면 400).
        질문은 배열로 보내고 답도 배열로 오며, 답의 `name`으로 질문을 찾음.
        예/아니오는 `predicate`. 질문 단위로 답을 거부(`refusal`)할 수 있음.
        응답 `model`에는 버전이 없음 (gpt-6-luna).
    """

    def _to_payload(self, request: DecisionRequest) -> dict:
        """공통 요청을 OpenAI 요청 본문으로 바꾼다.

        Args:
            request: 판단 요청.

        Returns:
            dict: JSON 요청 본문.
        """
        message = {"type": "message", "role": "user", "content": [{"type": "input_json", "data": request.subject}]}
        return {
            "model": request.model,
            "input": [message],
            "questions": [_question_payload(question) for question in request.questions],
        }

    def _usage_from_payload(self, body: dict) -> DecisionUsage:
        """OpenAI 응답 본문에서 모델·토큰 사용량을 읽는다.

        Args:
            body: JSON 응답 본문.

        Returns:
            DecisionUsage: 모델·토큰 사용량.

        Raises:
            KeyError: 필수 필드가 빠진 경우.
        """
        usage = body["usage"]
        input_details = usage.get("input_tokens_details") or {}
        return DecisionUsage(
            model=body["model"],
            input_tokens=usage["input_tokens"],
            cached_tokens=input_details.get("cached_tokens", 0),
            cache_write_tokens=input_details.get("cache_write_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    def _answers_from_payload(self, body: dict) -> dict[str, DecisionAnswer]:
        """OpenAI 응답 본문의 답을 질문 이름별 공통 답으로 바꾼다.

        Args:
            body: JSON 응답 본문.

        Returns:
            dict[str, DecisionAnswer]: 질문 이름별 답.

        Raises:
            KeyError: 필수 필드가 빠진 경우.
            ValueError: 모르는 답 종류이거나 값이 범위를 벗어난 경우.
        """
        return {answer["name"]: _answer(answer) for answer in body["answers"]}


def _question_payload(question: DecisionQuestion) -> dict:
    """질문 하나를 OpenAI 질문으로 바꾼다."""
    payload = {"name": question.name, "instructions": question.instructions}
    if isinstance(question, YesNoQuestion):
        return {"type": "predicate", **payload}
    if isinstance(question, ChoiceQuestion):
        return {"type": "choice", **payload, "choices": [_option("value", option) for option in question.options]}
    if isinstance(question, ScoreQuestion):
        return {"type": "score", **payload, "levels": [_option("label", level) for level in question.levels]}
    raise TypeError(f"모르는 질문 종류: {type(question).__name__}")


def _option(key: str, option: DecisionOption) -> dict:
    """후보·단계 하나를 OpenAI 형식으로 바꾼다. 설명이 없으면 뺌."""
    payload = {key: option.value}
    if option.description:
        payload["description"] = option.description
    return payload


def _answer(answer: dict) -> DecisionAnswer:
    """OpenAI 답 하나를 공통 답으로 바꾼다."""
    kind = answer.get("type")
    if kind == "predicate":
        return YesNoAnswer(probability=answer["probability"])
    if kind == "choice":
        return ChoiceAnswer(
            choice=answer["choice"],
            probabilities={item["value"]: item["probability"] for item in answer["probabilities"]},
            confidence=answer["confidence"],
        )
    if kind == "score":
        # value는 단계 번호 → 번호 순 리스트
        ordered = sorted(answer["probabilities"], key=lambda item: item["value"])
        return ScoreAnswer(
            score=answer["score"],
            probabilities=[item["probability"] for item in ordered],
            confidence=answer["confidence"],
        )
    if kind == "refusal":
        return RefusedAnswer()
    raise ValueError(f"모르는 OpenAI 답 종류: {kind!r}")
