"""TypeSafe 판단 형식 클라이언트 (Jev, `typesafe/jev-latest`)."""

import json

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
    DecisionUsage,
    ScoreAnswer,
    YesNoAnswer,
)
from .base import DecisionClient
from .errors import DecisionRequestError

# Jev가 받는 이미지 (게이트웨이 400 문구: base64 data URL, PNG·JPEG만)
_IMAGE_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/jpg;base64,")


class TypeSafeDecisionClient(DecisionClient):
    """TypeSafe 판단 형식 클라이언트.

    방식 : POST/JSON
    서비스 키 : ML API 키 (Authorization: Bearer)
    비고
        판단 대상은 `state`에 객체 그대로, 질문은 이름을 키로 한 맵으로 보냄.
        이미지가 있으면 `state`를 배열로 바꿔 판단 대상 JSON 글 뒤에 이미지 블록을 붙임.
        이미지는 base64 PNG·JPEG data URI만 받음 (http 주소·webp·긴 이미지 통째는 400).
        예/아니오는 `noul`, 점수 단계는 설명 문자열 배열(낮은 순)이고 답은 단계 번호로 옴.
        응답 `model`에 실제 버전이 옴 (예: typesafe/jev-1.14-20261014).
    """

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        """이미지 형식을 먼저 확인하고 질문을 보낸다. 나머지는 DecisionClient.decide와 같음.

        Args:
            request: 판단 요청.

        Returns:
            DecisionResponse: 질문 이름별 답과 토큰 사용량.

        Raises:
            DecisionRequestError: base64 PNG·JPEG data URI가 아닌 이미지가 있는 경우. 요청은 보내지 않음.
                그 밖은 DecisionClient.decide와 같음.
        """
        bad = [image[:40] for image in request.images if not image.startswith(_IMAGE_PREFIXES)]
        if bad:
            raise DecisionRequestError(f"Jev는 base64 PNG·JPEG data URI 이미지만 받음: {bad}")
        return super().decide(request)

    def _to_payload(self, request: DecisionRequest) -> dict:
        """공통 요청을 TypeSafe 요청 본문으로 바꾼다.

        Args:
            request: 판단 요청.

        Returns:
            dict: JSON 요청 본문.
        """
        return {
            "model": request.model,
            "state": _state(request),
            "questions": {question.name: _question_payload(question) for question in request.questions},
        }

    def _usage_from_payload(self, body: dict) -> DecisionUsage:
        """TypeSafe 응답 본문에서 모델·토큰 사용량을 읽는다.

        Args:
            body: JSON 응답 본문.

        Returns:
            DecisionUsage: 모델·토큰 사용량.

        Raises:
            KeyError: 필수 필드가 빠진 경우.
        """
        usage = body["usage"]
        return DecisionUsage(
            model=body["model"],
            input_tokens=usage["input_tokens"],
            cached_tokens=usage.get("cached_prompt_tokens", 0),
            cache_write_tokens=usage.get("cache_write_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    def _answers_from_payload(self, body: dict) -> dict[str, DecisionAnswer]:
        """TypeSafe 응답 본문의 답을 질문 이름별 공통 답으로 바꾼다.

        Args:
            body: JSON 응답 본문.

        Returns:
            dict[str, DecisionAnswer]: 질문 이름별 답.

        Raises:
            KeyError: 필수 필드가 빠진 경우.
            ValueError: 모르는 답 종류이거나 값이 범위를 벗어난 경우.
        """
        return {name: _answer(answer) for name, answer in body["answers"].items()}


def _state(request: DecisionRequest) -> dict | list[dict]:
    """판단 대상 정보와 이미지를 TypeSafe state로 바꾼다. 이미지가 없으면 객체 그대로."""
    if not request.images:
        return request.subject
    text ={"type": "text", "text": json.dumps(request.subject, ensure_ascii=False)}
    return [text] + [{"type": "image_url", "image_url": {"url": image}} for image in request.images]


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

