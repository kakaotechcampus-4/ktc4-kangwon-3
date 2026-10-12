"""별표 파싱 에이전트. 법령·행정규칙 별표 원문을 품목 행 레코드로 옮김.

진단 파이프라인이 아니라 적재 단계에서 법령 버전마다 한 번 실행.
흐름: 원문 다듬기 → 조각 나누기 → 조각별 모델 호출 → 병합 → 원문 대조.
"""

import json

from ..prompts import PromptName
from ..schemas.agents.annex import AnnexParseOutput, AnnexParseRecord, AnnexSource
from ..utils.annex_check import check_annex
from ..utils.annex_text import AnnexChunk, compact_annex, split_annex
from .base import AgentError, BaseAgent, MissingParsedOutput, ModelFailurePhase


class AnnexParsingError(AgentError):
    """조각 하나라도 모델 호출·파싱에 실패하면 발생. partial_result에 앞 조각까지 병합한 결과 보존."""


class AnnexParsingAgent(BaseAgent[AnnexParseOutput]):
    """별표 하나를 품목 행으로 파싱하고 원문과 대조한다.

    생성자는 BaseAgent 그대로. 평가 호출은 usage_agent("annex-parsing-eval" 등)로 나눠 집계함.
    """

    component_name = "annex_parsing"
    prompt_name = PromptName.ANNEX_PARSING
    output_schema = AnnexParseOutput
    error_class = AnnexParsingError
    structured_output_options = {"method": "json_schema", "strict": True}

    def parse(self, source: AnnexSource, content: str) -> AnnexParseRecord:
        """별표 원문을 파싱하고 원문 대조 결과와 함께 돌려준다.

        대조에 실패해도 예외로 끊지 않고 verified=False와 사유를 담아 돌려줌.
        적재 단계가 원문 조각으로 대체할지 정함.

        Args:
            source: 별표 출처.
            content: 별표 원문(별표내용). 다듬기 전 그대로.

        Returns:
            AnnexParseRecord: 병합한 출력, 원문 대조 결과, 실패 사유.

        Raises:
            AnnexParsingError: 조각 하나라도 모델 호출·파싱에 실패한 경우.
        """
        subject_id = f"{source.version_key}:별표{source.annex_number}-{source.annex_branch_number or '00'}"
        outputs: list[AnnexParseOutput] = []
        for chunk in split_annex(compact_annex(content)):
            partial = _merge(outputs) if outputs else None
            outputs.append(self._invoke(self._build_messages(source, chunk), subject_id=subject_id,
                                        partial_result=partial))
        output = _merge(outputs)
        # 원문 대조는 다듬기 전 원문 전체로
        reasons = check_annex(content, output)
        return AnnexParseRecord(source=source, output=output, verified=not reasons, failure_reasons=reasons)

    def _build_messages(self, source: AnnexSource, chunk: AnnexChunk) -> list:
        """출처·조각 원문·이어지는 문맥을 JSON 하나로 넣는다."""
        payload = {"source": source.model_dump(mode="json"), "content": chunk.content, "context": chunk.context}
        return self._messages(json.dumps(payload, ensure_ascii=False))

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """별표 파싱 실패 문구.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        if phase is ModelFailurePhase.CALL:
            return f"별표 파싱 모델 호출에 실패했습니다: {cause}"
        detail = None if isinstance(cause, MissingParsedOutput) else cause
        return f"모델 응답이 AnnexParseOutput 스키마와 맞지 않습니다: {detail}"


def _merge(outputs: list[AnnexParseOutput]) -> AnnexParseOutput:
    """조각 출력을 원문 순서대로 잇는다. scheme은 별표 제목이 든 첫 조각 기준, 같은 공통 비고는 한 번만."""
    return AnnexParseOutput(
        scheme=outputs[0].scheme,
        items=[item for output in outputs for item in output.items],
        skipped=[row for output in outputs for row in output.skipped],
        notes=list(dict.fromkeys(note for output in outputs for note in output.notes)),
    )
