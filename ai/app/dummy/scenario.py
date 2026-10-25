"""더미 시나리오. 접수 때 고른 시나리오를 입력 text_blocks에 표시로 남겨 재진단까지 이어 씀."""

import random
import re
from dataclasses import dataclass
from enum import StrEnum

from ..schemas.agent import ExtractionInput


class DummyFlow(StrEnum):
    """질문·실패 흐름."""

    NONE = "none"
    ONE_ROUND = "one_round"
    TWO_ROUNDS = "two_rounds"
    FAILED = "failed"
    FAILED_AFTER_ANSWER = "failed_after_answer"


class DummyResult(StrEnum):
    """완료 결과 종류. 공개 진단서 result_status 3종에 대응."""

    ALLOWED = "allowed"
    CERTIFICATION = "certification"
    RECHECK = "recheck"


@dataclass(frozen=True)
class DummyScenario:
    """상품 하나의 더미 시나리오.

    Attributes:
        flow: 질문·실패 흐름.
        result: 완료 결과 종류. 실패 흐름에선 쓰이지 않음.
    """

    flow: DummyFlow
    result: DummyResult


_MARKER_RE = re.compile(r"^\[dummy:flow=(\w+),result=(\w+)\]$")


def random_scenario(rng: random.Random | None = None) -> DummyScenario:
    """흐름·결과를 각각 무작위로 고른다.

    Args:
        rng: 난수 생성기. 테스트 고정용. 없으면 새로 만듦.

    Returns:
        DummyScenario: 고른 시나리오.
    """
    rng = rng or random.Random()
    return DummyScenario(flow=rng.choice(list(DummyFlow)), result=rng.choice(list(DummyResult)))


def mark_scenario(item: ExtractionInput, scenario: DummyScenario) -> ExtractionInput:
    """시나리오 표시를 text_blocks 끝에 붙인 입력을 만든다.

    Args:
        item: 상품 입력.
        scenario: 남길 시나리오.

    Returns:
        ExtractionInput: 표시가 붙은 새 입력.
    """
    marker = f"[dummy:flow={scenario.flow},result={scenario.result}]"
    return item.model_copy(update={"text_blocks": [*item.text_blocks, marker]})


def read_scenario(item: ExtractionInput) -> DummyScenario:
    """입력에 남긴 시나리오 표시를 읽는다.

    Args:
        item: mark_scenario로 표시를 붙인 상품 입력.

    Returns:
        DummyScenario: 표시된 시나리오.

    Raises:
        ValueError: 표시가 없거나 값이 잘못된 경우.
    """
    for block in reversed(item.text_blocks):
        if match := _MARKER_RE.match(block):
            return DummyScenario(flow=DummyFlow(match[1]), result=DummyResult(match[2]))
    raise ValueError(f"더미 시나리오 표시가 없습니다: {item.product_id}")
