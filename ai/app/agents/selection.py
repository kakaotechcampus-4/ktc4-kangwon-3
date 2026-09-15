"""선택 담당자가 구현하는 에이전트.

상품 정보(Product)를 받아 6개 심사 도메인 각각의 필요 여부를 판단한다.
툴 실행·재시도·결과 조립은 파이프라인의 책임이며 이 모듈은 선택만 돌려준다.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import build_chat_model
from ..schemas.agent import ToolSelectionResponse
from ..schemas.product import Product

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "selection.md"

logger = logging.getLogger(__name__)


class SelectionFailedError(RuntimeError):
    """LLM 호출 또는 구조화 출력 파싱 실패 시 발생하는 예외.

    호출부(파이프라인)가 langchain·openai SDK의 세부 예외를 알 필요 없이
    이 하나만 잡으면 된다. 원인 예외는 ``raise ... from exc``로 보존한다.
    """


class _StructuredSelector(Protocol):
    """``with_structured_output(include_raw=True)`` 반환 객체의 최소 인터페이스."""

    def invoke(self, messages: list) -> dict[str, Any]: ...


class _ModelLike(Protocol):
    """SelectionAgent 생성자가 받는 모델의 최소 인터페이스.

    ``BaseChatModel``과 테스트 스텁 모두 이 구조를 만족한다.
    """

    def with_structured_output(
        self, schema: type, *, include_raw: bool = ...
    ) -> _StructuredSelector: ...


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class SelectionAgent:
    """상품 정보를 보고 필요한 심사 도메인을 선택한다. 툴 실행은 파이프라인의 몫이다."""

    def __init__(self, model: _ModelLike | None = None) -> None:
        """선택 에이전트를 초기화한다.

        Args:
            model: 구조화 출력을 지원하는 LLM. None이면 build_chat_model()로 생성한다.
        """
        self._structured_model = (model or build_chat_model()).with_structured_output(
            ToolSelectionResponse, include_raw=True
        )

    def select(self, product: Product) -> ToolSelectionResponse:
        """추출된 상품 정보를 받아 6개 심사 도메인의 선택 여부를 판단한다.

        Args:
            product: 추출 에이전트가 만든 Product.

        Returns:
            6개 도메인 각각의 선택 여부와 이유를 담은 ToolSelectionResponse.

        Raises:
            SelectionFailedError: LLM 호출 실패 또는 응답이 스키마와 맞지 않을 때.
        """
        # 시스템 프롬프트와 Product JSON을 LLM 메시지 리스트로 조립한다. 
        messages = self._build_messages(product)

        try:
            # 조합한 메시지 리스트를 LLM에 보내고, 구조화된 응답과 원본 메시지를 받는다.
            result = self._structured_model.invoke(messages)

        except Exception as exc:
            # LLM 호출 실패 시 SelectionFailedError로 감싸서 호출부에 전달한다.
            raise SelectionFailedError(f"심사 도메인 선택에 실패했습니다: {exc}") from exc

        # 구조화 출력 파싱 중 발생한 예외. 정상 파싱이면 None.
        parsing_error = result.get("parsing_error")

        # 파싱된 ToolSelectionResponse 객체. 파싱 실패 시 None.
        selection = result.get("parsed")

        # 파싱 에러가 존재하거나 파싱 결과가 None인 경우
        if parsing_error is not None or selection is None:

            # 스키마 불일치로 간주하고 원인 예외를 체이닝하여 raise한다.
            raise SelectionFailedError(
                f"모델 응답이 ToolSelectionResponse 스키마와 맞지 않습니다: {parsing_error}"
            ) from parsing_error

        # LLM 응답의 토큰 사용량을 INFO 레벨로 기록한다.
        _log_token_usage(result.get("raw"))

        # 선택 결과를 반환한다.
        return selection

    @staticmethod
    def _build_messages(product: Product) -> list[SystemMessage | HumanMessage]:
        """시스템 프롬프트와 Product JSON을 LLM 메시지 리스트로 조립한다.

        Args:
            product: JSON 직렬화할 상품 정보.

        Returns:
            [SystemMessage(프롬프트), HumanMessage(상품 JSON)] 리스트.
        """
        # 추출 에이전트에게 받은 데이터를 JSON으로 직렬화한다.
        payload = product.model_dump(mode="json")

        # 시스템 프롬프트를 읽어오고 직렬화한 Product JSON과 함께 LLM 메시지 리스트를 반환한다.
        return [
            SystemMessage(content=_load_system_prompt()),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]


def _log_token_usage(raw_message: Any) -> None:
    """LLM 응답의 토큰 사용량을 INFO 레벨로 기록한다.

    Args:
        raw_message: ``with_structured_output(include_raw=True)``가 돌려주는 원본 AIMessage.
            usage_metadata가 없으면 아무것도 기록하지 않는다.
    """

    # raw_message에서 usage_metadata를 가져온다. 없으면 None.
    usage = getattr(raw_message, "usage_metadata", None)

    # usage_metadata가 없으면 아무것도 기록하지 않고 반환한다.
    if not usage:
        return

    # usage_metadata가 있으면 input_token_details를 가져온다. 없으면 빈 dict.
    input_details = usage.get("input_token_details") or {}

    # LLM 응답의 토큰 사용량을 INFO 레벨로 기록한다.
    logger.info(
        "선택 토큰 사용량 input=%s (cache_read=%s) output=%s total=%s",
        usage.get("input_tokens"),
        input_details.get("cache_read"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )

    # raw_message에서 response_metadata를 가져온다. 없으면 빈 dict.
    response_metadata = getattr(raw_message, "response_metadata", None) or {}

    # response_metadata에 token_usage가 있으면 DEBUG 레벨로 기록한다.
    if response_metadata.get("token_usage"):
        logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
