"""판단 모델(/decisions)로 6개 심사 도메인 선택 여부를 정하는 에이전트. 선택 에이전트와 출력이 같음."""

import logging
from typing import Any

from ...clients.llm.decision import DecisionClient
from ...config import ConfigError
from ...schemas.agent import ToolSelectionResponse
from ...schemas.product import Product
from ..base import AgentResult, BaseAgent
from .assemble import assemble, assemble_without_answers
from .errors import DecisionSelectionFailedError
from .questions import QUESTIONS
from .thresholds import THRESHOLDS

logger = logging.getLogger(__name__)

# 판단에 안 쓰는 식별 필드
_NOT_SUBJECT = {"product_id", "source_url"}


class DecisionSelectionAgent(BaseAgent[Product, ToolSelectionResponse, ToolSelectionResponse]):
    """상품 정보를 코드 규칙과 판단 모델 답으로 보고 6개 심사 도메인 각각의 선택 여부와 이유를 낸다.

    채팅 모델·시스템 프롬프트 없이 판단 모델만 한 번 호출. 평가 호출은 usage_agent로 운영 비용과 구분.
    """

    component_name = "decision_selection"
    error_class = DecisionSelectionFailedError
    task_name = "심사 도메인 선택"
    creates_default_model = False

    def __init__(
        self, *, usage_agent: str | None = None, decision_client: DecisionClient | None = None,
        decision_model: str | None = None,
    ) -> None:
        """판단 모델과 문턱값이 정해졌는지 확인하고 에이전트를 만든다.

        Args:
            usage_agent: 사용량 기록 이름. None이면 component_name.
            decision_client: 판단 클라이언트. None이면 판단 프로필로 고름.
            decision_model: 판단 모델 등록명. decision_client를 주면 필수.

        Raises:
            ConfigError: 판단 프로필이 없거나, 판단 모델의 문턱값이 정해지지 않은 경우.
            ValueError: decision_client만 주고 decision_model을 안 준 경우.
        """
        super().__init__(usage_agent=usage_agent, decision_client=decision_client, decision_model=decision_model)
        if self._decision_model is None:
            raise ConfigError(f"{self.component_name}: 판단 모델 프로필이 정해지지 않았습니다.")
        if self._decision_model not in THRESHOLDS:
            raise ConfigError(f"{self.component_name}: 문턱값이 정해지지 않은 판단 모델입니다: {self._decision_model}")

    def run_with_meta(self, input: Product) -> AgentResult[ToolSelectionResponse]:
        """판단 모델에 질문 한 묶음을 보내고 답으로 선택 결과를 조립한다.

        판단 호출이 실패하면 실패로 기록한 뒤 규칙에 안 걸린 Tool까지 모두 선택한 결과를 돌려줌.

        Args:
            input: 추출된 상품 정보.

        Returns:
            AgentResult[ToolSelectionResponse]: 6개 Tool 선택 결과와 실행 정보. 판단 호출 실패 시 실행 정보는
            실패 기록 (``failure_phase`` 있음).
        """
        subject_id = self._subject_id(input)
        questions = list(QUESTIONS)
        subject = input.model_dump(mode="json", exclude=_NOT_SUBJECT)
        try:
            response, usage, started_at = self._call_decision(subject, questions, subject_id=subject_id)
        except DecisionSelectionFailedError as exc:
            # 호출 실패는 이미 기록됨. 선택을 비우면 진단이 멈추므로 모르면 선택(원칙 1)으로 이어감
            logger.warning("판단 선택 호출 실패, 전부 선택으로 대체: %s", exc)
            return AgentResult(assemble_without_answers(input), exc.meta)
        try:
            result = assemble(input, response.answers, self._decision_model)
        except Exception as exc:
            self._fail_after_call(exc, usage, subject_id, started_at, decision_questions=questions)
        meta = self._finish_call(usage, subject_id, started_at, decision_questions=questions)
        return AgentResult(result, meta)

    def _subject_id(self, input: Product) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 추출된 상품 정보.

        Returns:
            str: 상품 ID.
        """
        return input.product_id

    def _build_messages(self, input: Product) -> list[Any]:
        """채팅 모델을 안 써 쓰지 않음.

        Raises:
            NotImplementedError: 항상.
        """
        raise NotImplementedError(f"{self.component_name}: 판단 모델만 써 채팅 메시지가 없습니다.")
