"""진단 입력(상품 글·이미지, 재질문 답변)에 진단을 조작하려는 지시가 있는지 보는 에이전트.

순서: 형식 규칙(모델 호출 없음) → 글 판단 1회 → 이미지 판단(장마다 따로, 병렬).
한 번에 여러 조각을 넣으면 한 조각의 지시가 다른 조각에 묻혀 점수가 흐려짐 (11-04 실측 0.89 → 0.59~0.74).
일시 오류(429·5xx·연결 실패) 재시도는 판단 클라이언트가 맡음.
그래도 실패하면 그 부분은 못 본 것으로 두고 나머지로 판정하되, 통과 대신 의심으로 남김 (진단은 막지 않음).
받기·읽기 실패나 상한 초과로 건너뛴 이미지가 있을 때도 같음.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field, replace
from enum import Enum
from time import perf_counter
from typing import Any

from ...clients.llm.decision import DecisionClient
from ...config import ConfigError, ReviewThresholds, get_settings
from ...observability.trace import current_trace
from ..base import AgentResult, BaseAgent
from .errors import InputGuardFailedError
from .format_rules import format_hits
from .images import prepare_judge_images
from .questions import QUESTION_NAME, QUESTIONS

logger = logging.getLogger(__name__)

# 이미지 판단 동시 호출 수
MAX_PARALLEL_IMAGES = 10
# 이미지와 같이 보내는 판단 대상 설명
_IMAGE_SUBJECT = {"input": "상품 상세 이미지"}


class GuardOutcome(str, Enum):
    """가드 판정."""

    PASS = "pass"
    SUSPECT = "suspect"
    BLOCK = "block"


@dataclass(frozen=True)
class GuardInput:
    """가드 입력 하나.

    Attributes:
        product_id: 상품 ID. 사용량 기록 대상.
        texts: 상품 글 블록 또는 재질문 답변. 비면 글 판단을 건너뜀.
        image_urls: 이미지 주소 또는 data URI. 비면 이미지 판단을 건너뜀.
    """

    product_id: str
    texts: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GuardVerdict:
    """가드 판정 결과.

    Attributes:
        outcome: 통과·의심·차단.
        format_hits: 걸린 형식 규칙 이름. 걸리면 모델을 부르지 않고 차단.
        text_score: 글 판단 점수. 글이 없거나 판단하지 못했으면 None.
        image_scores: 판단 이미지별 점수 (조각 포함, 순서대로). 판단하지 못한 이미지는 None.
        skipped_images: 받기·읽기 실패나 상한으로 못 본 원래 이미지 수.
        failed_calls: 실패한 판단 호출 수.
    """

    outcome: GuardOutcome
    format_hits: list[str] = field(default_factory=list)
    text_score: float | None = None
    image_scores: list[float | None] = field(default_factory=list)
    skipped_images: int = 0
    failed_calls: int = 0

    @property
    def image_score(self) -> float | None:
        """판단한 이미지 중 가장 높은 점수. 판단한 이미지가 없으면 None."""
        scores = [score for score in self.image_scores if score is not None]
        return max(scores) if scores else None


class InputGuardAgent(BaseAgent[GuardInput, None, GuardVerdict]):
    """진단 입력을 형식 규칙과 판단 모델로 보고 통과·의심·차단을 정한다.

    채팅 모델·시스템 프롬프트 없이 판단 모델만 씀. 호출마다 사용량을 따로 기록.
    """

    component_name = "input_guard"
    error_class = InputGuardFailedError
    task_name = "입력 확인"
    creates_default_model = False

    def __init__(
        self, *, thresholds: ReviewThresholds | None = None, usage_agent: str | None = None,
        decision_client: DecisionClient | None = None, decision_model: str | None = None,
    ) -> None:
        """문턱값과 판단 모델이 정해졌는지 확인하고 에이전트를 만든다.

        Args:
            thresholds: 문턱값. None이면 설정(REVIEW_*)에서 읽음.
            usage_agent: 사용량 기록 이름. None이면 component_name.
            decision_client: 판단 클라이언트. None이면 판단 프로필로 고름.
            decision_model: 판단 모델 등록명. decision_client를 주면 필수.

        Raises:
            ConfigError: 문턱값이나 판단 프로필이 정해지지 않은 경우.
            ValueError: decision_client만 주고 decision_model을 안 준 경우.
        """
        super().__init__(usage_agent=usage_agent, decision_client=decision_client, decision_model=decision_model)
        if self._decision_model is None:
            raise ConfigError(f"{self.component_name}: 판단 모델 프로필이 정해지지 않았습니다.")
        self._thresholds = thresholds or get_settings().review_thresholds
        if self._thresholds is None:
            raise ConfigError(f"{self.component_name}: 문턱값(REVIEW_*)이 정해지지 않았습니다.")

    def run_with_meta(self, input: GuardInput) -> AgentResult[GuardVerdict]:
        """형식 규칙 → 글 판단 → 이미지 판단 순서로 보고 판정한다. 차단이 정해지면 뒤 단계는 건너뜀.

        Args:
            input: 가드 입력.

        Returns:
            AgentResult[GuardVerdict]: 판정과 실행 정보. 판단 호출은 호출마다 따로 기록되어, 실행 정보는
            전체 걸린 시간만 담음.
        """
        started_at = perf_counter()
        hits = format_hits("\n".join(input.texts))
        if hits:
            return self._result(GuardVerdict(outcome=GuardOutcome.BLOCK, format_hits=hits), started_at)

        failed = 0
        text_score = None
        if input.texts:
            text_score = self._score({"text_blocks": input.texts}, input.product_id)
            failed += text_score is None
        if text_score is not None and text_score >= self._thresholds.text_high:
            return self._result(
                GuardVerdict(outcome=GuardOutcome.BLOCK, text_score=text_score, failed_calls=failed), started_at,
            )

        prepared = prepare_judge_images(input.image_urls) if input.image_urls else None
        image_scores = self._image_scores(prepared.images, input.product_id) if prepared else []
        failed += sum(score is None for score in image_scores)
        verdict = GuardVerdict(
            outcome=GuardOutcome.PASS, text_score=text_score, image_scores=image_scores,
            skipped_images=prepared.skipped if prepared else 0, failed_calls=failed,
        )
        return self._result(_with_outcome(verdict, self._thresholds), started_at)

    def _score(self, subject: dict[str, Any], product_id: str, images: list[str] | None = None) -> float | None:
        """판단 모델로 조작 지시가 있을 확률을 받는다. 실패하면 None (일시 오류 재시도는 클라이언트가 함).

        실패한 호출은 이미 기록됨.

        Args:
            subject: 판단 대상 정보.
            product_id: 사용량 기록 대상 ID.
            images: 같이 볼 이미지.

        Returns:
            float | None: "예"일 확률. 호출·응답 변환 실패나 답 거부면 None.
        """
        questions = list(QUESTIONS)
        try:
            response, usage, started_at = self._call_decision(
                subject, questions, subject_id=product_id, images=images,
            )
        except InputGuardFailedError as exc:
            logger.warning("입력 확인 판단 실패, 이 부분은 넘김: %s", exc)
            return None
        self._finish_call(usage, product_id, started_at, decision_questions=questions)
        return getattr(response.answers[QUESTION_NAME], "probability", None)

    def _image_scores(self, images: list[str], product_id: str) -> list[float | None]:
        """이미지마다 따로 판단한다. trace 기록 중에는 호출 기록이 섞이지 않게 차례로.

        Args:
            images: 판단 이미지 (JPEG data URI).
            product_id: 사용량 기록 대상 ID.

        Returns:
            list[float | None]: 이미지별 점수 (순서대로).
        """
        def score(image: str) -> float | None:
            return self._score(_IMAGE_SUBJECT, product_id, [image])

        if current_trace() is not None or len(images) <= 1:
            return [score(image) for image in images]
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_IMAGES, len(images))) as executor:
            # 실행 정보(로그 문맥)를 스레드로 넘김
            futures = [executor.submit(copy_context().run, score, image) for image in images]
            return [future.result() for future in futures]

    def _result(self, verdict: GuardVerdict, started_at: float) -> AgentResult[GuardVerdict]:
        """판정에 전체 걸린 시간을 담은 실행 정보를 붙인다."""
        meta = self._run_meta(
            elapsed_ms=round((perf_counter() - started_at) * 1000), decision_questions=list(QUESTIONS),
        )
        return AgentResult(verdict, meta)

    def _subject_id(self, input: GuardInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 가드 입력.

        Returns:
            str: 상품 ID.
        """
        return input.product_id

    def _build_messages(self, input: GuardInput) -> list[Any]:
        """채팅 모델을 안 써 쓰지 않음.

        Raises:
            NotImplementedError: 항상.
        """
        raise NotImplementedError(f"{self.component_name}: 판단 모델만 써 채팅 메시지가 없습니다.")


def _with_outcome(verdict: GuardVerdict, thresholds: ReviewThresholds) -> GuardVerdict:
    """점수와 문턱값으로 판정을 채운다. 판단 못 한 부분이 있으면 통과 대신 의심.

    Args:
        verdict: 점수를 채운 판정 (outcome은 무시).
        thresholds: 문턱값.

    Returns:
        GuardVerdict: 판정을 채운 결과.
    """
    text, image = verdict.text_score, verdict.image_score
    if (text is not None and text >= thresholds.text_high) or (image is not None and image >= thresholds.image_high):
        return replace(verdict, outcome=GuardOutcome.BLOCK)
    if (text is not None and text >= thresholds.text_low) or (image is not None and image >= thresholds.image_low):
        return replace(verdict, outcome=GuardOutcome.SUSPECT)
    # 못 본 부분에 지시가 있을 수 있어 경고 로그로 남김
    if verdict.failed_calls or verdict.skipped_images:
        return replace(verdict, outcome=GuardOutcome.SUSPECT)
    return replace(verdict, outcome=GuardOutcome.PASS)
