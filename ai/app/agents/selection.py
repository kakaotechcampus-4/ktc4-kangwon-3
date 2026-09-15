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
    """LLM 호출 또는 구조화 출력 파싱이 실패했을 때 발생한다.

    레이트리밋·인증 오류·스키마 불일치 등 원인은 다양하지만, 호출부(파이프라인)는
    langchain·openai SDK의 세부 예외 타입을 알 필요 없이 이 하나만 잡으면 된다.
    원인 예외는 ``raise ... from exc``로 보존해 traceback에서 근본 원인을 확인할 수 있다.
    """


class _StructuredSelector(Protocol):
    """``model.with_structured_output(..., include_raw=True)``가 돌려주는 결과물의 최소 인터페이스."""

    def invoke(self, messages: list) -> dict[str, Any]: ...


class _ModelLike(Protocol):
    """SelectionAgent가 실제로 쓰는 메서드만 좁혀 놓은 타입.

    ``BaseChatModel``은 이 구조를 만족하므로 실제 모델도 그대로 넘길 수 있고,
    테스트에서는 ``BaseChatModel``을 상속하지 않는 가벼운 스텁도 그대로 넘길 수 있다.
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
        self._structured_model = (model or build_chat_model()).with_structured_output(
            ToolSelectionResponse, include_raw=True
        )

    def select(self, product: Product) -> ToolSelectionResponse:
        """
        입력: 추출 에이전트가 만든 Product
        출력: 6개 도메인 각각의 선택 여부와 이유를 담은 ToolSelectionResponse

        raises SelectionFailedError: LLM 호출·구조화 출력 파싱이 실패한 경우.
        """
        messages = self._build_messages(product)
        try:
            result = self._structured_model.invoke(messages)
        except Exception as exc:
            raise SelectionFailedError(f"심사 도메인 선택에 실패했습니다: {exc}") from exc

        parsing_error = result.get("parsing_error")
        selection = result.get("parsed")
        if parsing_error is not None or selection is None:
            raise SelectionFailedError(
                f"모델 응답이 ToolSelectionResponse 스키마와 맞지 않습니다: {parsing_error}"
            ) from parsing_error

        _log_token_usage(result.get("raw"))
        return selection

    @staticmethod
    def _build_messages(product: Product) -> list[SystemMessage | HumanMessage]:
        payload = product.model_dump(mode="json")
        return [
            SystemMessage(content=_load_system_prompt()),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]


def _log_token_usage(raw_message: Any) -> None:
    usage = getattr(raw_message, "usage_metadata", None)
    if not usage:
        return
    input_details = usage.get("input_token_details") or {}
    logger.info(
        "선택 토큰 사용량 input=%s (cache_read=%s) output=%s total=%s",
        usage.get("input_tokens"),
        input_details.get("cache_read"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )
    response_metadata = getattr(raw_message, "response_metadata", None) or {}
    if response_metadata.get("token_usage"):
        logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])
