"""판단 API(/decisions) 응답 모델. 모델별 응답을 공통 모양으로 바꾼 결과."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class YesNoAnswer(BaseModel):
    """예/아니오 질문의 답.

    Attributes:
        type: 답 종류.
        probability: "예"일 확률.
    """

    type: Literal["yes_no"] = "yes_no"
    probability: float = Field(ge=0, le=1)


class ChoiceAnswer(BaseModel):
    """고르기 질문의 답.

    Attributes:
        type: 답 종류.
        choice: 고른 후보 값.
        probabilities: 후보 값별 확률.
        confidence: 모델이 낸 확신도.
    """

    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)


class ScoreAnswer(BaseModel):
    """점수 질문의 답.

    Attributes:
        type: 답 종류.
        score: 단계 확률로 낸 기댓값 점수 (단계 번호 기준, 0부터).
        probabilities: 단계별 확률. 요청 단계 순서(낮은 단계부터).
        confidence: 모델이 낸 확신도.
    """

    type: Literal["score"] = "score"
    score: float
    probabilities: list[float]
    confidence: float = Field(ge=0, le=1)


class RefusedAnswer(BaseModel):
    """모델이 답을 거부한 질문.

    Attributes:
        type: 답 종류.
    """

    type: Literal["refused"] = "refused"


DecisionAnswer = Annotated[
    YesNoAnswer | ChoiceAnswer | ScoreAnswer | RefusedAnswer,
    Field(discriminator="type"),
]


class DecisionUsage(BaseModel):
    """판단 응답 하나의 모델·토큰 사용량. 답을 해석하지 못해도 따로 읽어 비용을 남김.

    Attributes:
        model: 응답이 알려 준 실제 모델 이름 (Jev는 버전 포함).
        input_tokens: 입력 토큰 수.
        cached_tokens: 캐시에서 읽은 입력 토큰 수.
        cache_write_tokens: 캐시에 쓴 입력 토큰 수.
        output_tokens: 출력 토큰 수. 두 모델 모두 과금 안 함.
    """

    model: str
    input_tokens: int = Field(ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class DecisionResponse(BaseModel):
    """판단 응답 하나.

    Attributes:
        answers: 질문 이름별 답.
        usage: 모델·토큰 사용량.
    """

    answers: dict[str, DecisionAnswer]
    usage: DecisionUsage
