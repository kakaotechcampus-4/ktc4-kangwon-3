"""판단 API(/decisions) 요청 모델. 모델별 형식(Jev·Luna)과 무관한 공통 모양."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class DecisionOption(BaseModel):
    """고르기 후보 또는 점수 단계 하나.

    Args:
        value: 후보 값 또는 단계 이름. 답에서 이 값으로 돌아옴.
        description: 후보·단계 설명. 없으면 값만 보냄.
    """

    value: str = Field(min_length=1)
    description: str | None = None


class YesNoQuestion(BaseModel):
    """예/아니오 질문. 답은 "예"일 확률 (Jev noul, Luna predicate).

    Args:
        type: 질문 종류.
        name: 질문 이름. 답을 이 이름으로 찾음.
        instructions: 질문 지침.
    """

    type: Literal["yes_no"] = "yes_no"
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1)


class ChoiceQuestion(BaseModel):
    """후보 중 하나를 고르는 질문. 답은 고른 값과 후보별 확률.

    Args:
        type: 질문 종류.
        name: 질문 이름. 답을 이 이름으로 찾음.
        instructions: 질문 지침.
        options: 후보. Luna가 2개 이상, 두 모델 모두 255개까지 받음.
    """

    type: Literal["choice"] = "choice"
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    options: list[DecisionOption] = Field(min_length=2, max_length=255)


class ScoreQuestion(BaseModel):
    """순서 있는 단계로 매기는 질문. 답은 단계별 확률과 기댓값 점수.

    Args:
        type: 질문 종류.
        name: 질문 이름. 답을 이 이름으로 찾음.
        instructions: 질문 지침.
        levels: 단계. 낮은 단계부터, 두 모델 모두 2개에서 10개.
    """

    type: Literal["score"] = "score"
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    levels: list[DecisionOption] = Field(min_length=2, max_length=10)


DecisionQuestion = Annotated[
    YesNoQuestion | ChoiceQuestion | ScoreQuestion,
    Field(discriminator="type"),
]


class DecisionRequest(BaseModel):
    """판단 요청 하나. 모든 질문은 같은 판단 대상 정보를 봄.

    Args:
        model: 카탈로그 모델 이름 (예: "typesafe/jev-latest", "openai/gpt-6-luna").
        subject: 판단 대상 정보 (예: 상품 정보). Jev는 state, Luna는 JSON 입력으로 보냄.
        questions: 질문 목록. Luna가 400개까지 받음.
    """

    model: str = Field(min_length=1)
    subject: dict[str, Any]
    questions: list[DecisionQuestion] = Field(min_length=1, max_length=400)
