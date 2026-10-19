"""에이전트 공통 실행 인터페이스. 클라이언트의 fetch_parsed/_send/_parse와 같은 구조.

공개 입구는 ``run``·``run_with_meta`` 둘뿐이고, 하위 클래스는 입력 → 메시지(``_build_messages``)와
사용량 기록 대상(``_subject_id``)만 구현함. 필요할 때만 ``_finalize``·``_skip``을 다시 정의.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic

from .agent import BaseAgent
from .errors import MissingParsedOutput, ModelFailurePhase
from .meta import AgentResult
from .protocols import InputT, OutputT, ResultT


class Agent(BaseAgent[OutputT], ABC, Generic[InputT, OutputT, ResultT]):
    """입력 하나로 모델을 한 번 호출해 결과를 내는 에이전트.

    Attributes:
        task_name: 호출 실패 문구에 쓸 작업 이름 (예: "상품 정보 추출"). (필수)
        output_label: 파싱 실패 문구에 쓸 출력 이름. None이면 output_schema 클래스 이름.
    """

    task_name: ClassVar[str]
    output_label: ClassVar[str | None] = None

    def run(self, input: InputT) -> ResultT:
        """입력을 처리해 결과를 돌려준다.

        Args:
            input: 에이전트 입력.

        Returns:
            ResultT: 에이전트 결과.

        Raises:
            AgentError: 모델 호출·파싱 실패. 실제 타입은 ``error_class``.
        """
        return self.run_with_meta(input).result

    def run_with_meta(self, input: InputT) -> AgentResult[ResultT]:
        """입력을 처리해 결과와 실행 정보를 돌려준다.

        흐름: ``_skip`` → ``_build_messages`` → 모델 호출 → ``_finalize``.

        Args:
            input: 에이전트 입력.

        Returns:
            AgentResult[ResultT]: 결과와 실행 정보. 모델 없이 끝났으면 사용량 없는 실행 정보.

        Raises:
            AgentError: 모델 호출·파싱 실패. 실제 타입은 ``error_class``, 실행 정보는 ``meta``.
        """
        skipped = self._skip(input)
        # 모델 호출 없이 결과가 정해지는 입력 (예: 이미지 0장)
        if skipped is not None:
            return AgentResult(skipped, self._run_meta())
        output, meta = self._invoke_with_meta(self._build_messages(input), subject_id=self._subject_id(input))
        return AgentResult(self._finalize(output, input), meta)

    @abstractmethod
    def _build_messages(self, input: InputT) -> list[Any]:
        """입력을 모델 메시지로 만든다.

        Args:
            input: 에이전트 입력.

        Returns:
            list[Any]: 모델에 보낼 메시지.
        """

    @abstractmethod
    def _subject_id(self, input: InputT) -> str:
        """사용량 기록 대상 ID를 고른다.

        Args:
            input: 에이전트 입력.

        Returns:
            str: 기록 대상 ID (보통 상품 ID).
        """

    def _finalize(self, output: OutputT, input: InputT) -> ResultT:
        """모델 출력을 최종 결과로 바꾼다. 기본은 출력 그대로.

        Args:
            output: 검증된 모델 출력.
            input: 에이전트 입력.

        Returns:
            ResultT: 최종 결과.
        """
        return output  # type: ignore[return-value]

    def _skip(self, input: InputT) -> ResultT | None:
        """모델 호출 없이 정해지는 결과를 돌려준다. 기본은 None(항상 호출).

        Args:
            input: 에이전트 입력.

        Returns:
            ResultT | None: 호출 없이 낼 결과. 호출해야 하면 None.
        """
        return None

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 문구를 만든다. 호출 실패는 작업 이름, 파싱 실패는 출력 이름으로.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        # 응답을 못 받은 실패
        if phase is ModelFailurePhase.CALL:
            return f"{self.task_name}에 실패했습니다: {cause}"
        # 빈 출력이면 원인 자리에 None (기존 문구 유지)
        detail = None if isinstance(cause, MissingParsedOutput) else cause
        label = self.output_label or self.output_schema.__name__
        return f"모델 응답이 {label} 스키마와 맞지 않습니다: {detail}"
