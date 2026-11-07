"""진단을 trace에 남기는 것. 기록 중이 아니면 원래와 똑같이 동작함.

- 단계 trace hook: 단계마다 trace 단계를 열고 나온 값(output)을 원래 모양 그대로 남김.
  다음 단계의 입력은 앞 단계의 output이라 따로 안 남김 (추출 입력만 남김). 재실행 회차는 단계마다 round로.
- 이미지 자르기: 부품 파일(pipeline/)은 고치지 않고, 조립(assembly.py)에서 감싼 부품을 넣음.
"""

from collections.abc import Callable
from contextvars import ContextVar
from typing import TypeVar

from ..observability.trace import current_trace, image_link, trace_alias, trace_note, trace_step
from ..pipeline.hooks import StageName
from ..pipeline.image_split import ImageSplitter
from ..schemas.pipeline import SelectionResult
from ..schemas.schemas import DraftAssessment, VerificationResult
from ..schemas.session import DiagnosisInput

T = TypeVar("T")

# 재실행 회차가 없어 trace 단계에 round를 안 남기는 단계
_FIRST_ROUND_ONLY = ("extraction", "selection")


class TraceStageHook:
    """단계마다 trace 단계를 열고 output을 남김. 추출 단계엔 실행 입력도."""

    def __init__(self, job_input: DiagnosisInput) -> None:
        """
        Args:
            job_input: 이번 실행 입력. 추출 단계 input으로 남김.
        """
        self._job_input = job_input

    def __call__(self, stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
        fields = {} if stage in _FIRST_ROUND_ONLY else {"round": retry_round}
        with trace_step(stage, **fields):
            if stage == "extraction":
                trace_note("input", self._job_input)
            result = call()
            alias_ids(result)
            trace_note("output", result)
        return result


def alias_ids(value: object) -> None:
    """실행마다 달라지는 ID(uuid)를 trace 저장 때 실행 안 번호로 바꾸게 등록한다. 기록 중이 아니면 아무것도 안 함.

    Tool 실행 ID는 e, 진단서 ID는 a, 검증 지적 ID는 i, 재질문 ID는 q (판단 ID f는 Tool 기록에서). 두 실행 diff 비교용.

    Args:
        value: 단계 결과 (Tool 실행 결과·종합 초안·검증 결과). 그 밖의 값은 무시.
    """
    if isinstance(value, SelectionResult):
        for result in (*value.tool_results, *value.tool_result_history):
            if result.execution_id:
                trace_alias(result.execution_id, "e")
    elif isinstance(value, DraftAssessment):
        trace_alias(value.assessment_id, "a")
        for question in value.follow_up_questions:
            trace_alias(question.question_id, "q")
    elif isinstance(value, VerificationResult):
        for issue in value.issues:
            trace_alias(issue.issue_id, "i")
        for question in value.follow_up_questions:
            trace_alias(question.question_id, "q")

# prepare 한 번 동안 이미지마다 조각 수 (자르지 않으면 None). 여러 진단이 부품을 같이 써서 문맥 변수로
_tile_counts: ContextVar[list[int | None] | None] = ContextVar("image_tile_counts", default=None)


class TracedImageSplitter(ImageSplitter):
    """긴 이미지 자르기 전후를 trace에 남기는 이미지 자르기. 자르는 동작은 그대로.

    이미지마다 결과를 남김.
        - split: 조각으로 나눔 (조각 수)
        - not_split: 짧은 이미지거나 받기·읽기 실패 (둘은 구분 안 됨, 실패는 경고 로그)
        - over_limit: 길지만 상품당 조각 수 상한을 넘어 원래 주소로 넘김
    """

    def prepare(self, image_urls: list[str]) -> list[str]:
        """긴 이미지만 조각으로 바꾼 이미지 주소 목록을 만들고, 기록 중이면 이미지별 결과를 남긴다.

        Args:
            image_urls: http(s) 주소 또는 data URI.

        Returns:
            list[str]: 짧은 이미지는 원래 주소, 긴 이미지는 조각 data URI.
        """
        if current_trace() is None:
            return super().prepare(image_urls)
        counts: list[int | None] = []
        token = _tile_counts.set(counts)
        try:
            prepared = super().prepare(image_urls)
        finally:
            _tile_counts.reset(token)
        trace_note("image_split", {
            "images": _image_results(image_urls, counts, self._max_tiles),
            "sent": len(prepared),
        })
        return prepared

    def _tiles(self, url: str) -> list[bytes] | None:
        tiles = super()._tiles(url)
        counts = _tile_counts.get()
        if counts is not None:
            counts.append(None if tiles is None else len(tiles))
        return tiles


def _image_results(image_urls: list[str], counts: list[int | None], max_tiles: int) -> list[dict]:
    """이미지별 자르기 결과. 상한 판단은 ImageSplitter.prepare와 같은 순서로 셈.

    Args:
        image_urls: 원래 이미지 주소.
        counts: 이미지마다 조각 수 (자르지 않으면 None).
        max_tiles: 상품당 조각 수 상한.

    Returns:
        list[dict]: 주소·결과·조각 수.
    """
    results: list[dict] = []
    total = 0
    for url, count in zip(image_urls, counts):
        if count is None:
            results.append({"url": image_link(url), "result": "not_split"})
        elif total + count > max_tiles:
            results.append({"url": image_link(url), "result": "over_limit", "tiles": count})
        else:
            total += count
            results.append({"url": image_link(url), "result": "split", "tiles": count})
    return results
