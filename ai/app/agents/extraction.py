"""추출 담당자가 구현하는 에이전트."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..schemas.agent import ExtractionInput
from ..schemas.product import ExtractedProductFields, Product

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extraction.md"


class ExtractionFailedError(RuntimeError):
    """LLM 호출 또는 구조화 출력 파싱이 실패했을 때 발생한다.

    레이트리밋·인증 오류·스키마 불일치 등 원인은 다양하지만, 호출부(파이프라인)는
    langchain·openai SDK의 세부 예외 타입을 알 필요 없이 이 하나만 잡으면 된다.
    원인 예외는 ``raise ... from exc``로 보존해 traceback에서 근본 원인을 확인할 수 있다.
    """


class _StructuredExtractor(Protocol):
    """``model.with_structured_output(...)``가 돌려주는 결과물의 최소 인터페이스."""

    def invoke(self, messages: list) -> ExtractedProductFields: ...


class _ModelLike(Protocol):
    """ExtractionAgent가 실제로 쓰는 메서드만 좁혀 놓은 타입.

    ``BaseChatModel``은 이 구조를 만족하므로 실제 모델도 그대로 넘길 수 있고,
    테스트에서는 ``BaseChatModel``을 상속하지 않는 가벼운 스텁도 그대로 넘길 수 있다.
    """

    def with_structured_output(self, schema: type[ExtractedProductFields]) -> _StructuredExtractor: ...


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    # extract() 호출마다 디스크를 다시 읽지 않도록 캐싱한다. 프롬프트 파일은 배포 중 안 바뀐다.
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _default_model() -> BaseChatModel:
    # 모듈 import 시 외부 서비스에 연결하지 않는다(app/__init__.py 규칙).
    # 그래서 .env 로드와 클라이언트 생성 모두 실제로 에이전트를 만들 때(__init__)만 실행한다.
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI

    load_dotenv()
    # 카카오테크캠퍼스 엘리스 AI클라우드의 MLAPI(Serverless)를 사용한다.
    # OpenAI 공식 서버(api.openai.com)가 아니라 이 base_url로 요청이 가야 인증이 통과한다.
    # 모델 이름도 카탈로그 등록명인 "openai/gpt-4.1-mini" 형식을 그대로 써야 한다.
    model_name = os.environ.get("OPENAI_MODEL", "openai/gpt-4.1-mini")
    base_url = os.environ.get("OPENAI_BASE_URL")
    return ChatOpenAI(model=model_name, base_url=base_url, temperature=0)


class ExtractionAgent:
    """상품 원문에서 정보를 추출한다. 툴 선택이나 규제 판정은 맡지 않는다."""

    def __init__(self, model: _ModelLike | None = None) -> None:
        # model을 주입하면 테스트에서 실제 API 호출 없이 검증할 수 있다.
        self._structured_model = (model or _default_model()).with_structured_output(
            ExtractedProductFields
        )

    def extract(self, source: ExtractionInput) -> Product:
        """
        입력: 수집된 상품 텍스트·이미지 참조
        출력: 상품 정보와 15개 상품 속성(6개 심사 툴 선택에 참고할 신호)을 담은 Product

        raises ExtractionFailedError: LLM 호출·구조화 출력 파싱이 실패한 경우.
            text_blocks·image_urls가 모두 비어 입력 자체가 없는 경우는 ValueError.
        """
        messages = self._build_messages(source)
        try:
            fields = self._structured_model.invoke(messages)
        except Exception as exc:
            # langchain·openai SDK의 구체적인 예외 타입(레이트리밋·인증 오류·검증 실패 등)을
            # 호출부가 몰라도 되게 하나로 감싼다. 여기서 삼키지 않고 원인은 그대로 보존한다.
            raise ExtractionFailedError(f"상품 정보 추출에 실패했습니다: {exc}") from exc
        # product_id·source_url은 모델이 만들지 않는다. 요청 값을 그대로 옮긴다.
        return Product(
            product_id=source.product_id,
            source_url=source.source_url,
            **fields.model_dump(),
        )

    def _build_messages(self, source: ExtractionInput) -> list[SystemMessage | HumanMessage]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": block} for block in source.text_blocks
        ]
        # http(s) URL과 data:image/...;base64,... 문자열을 동일하게 다룬다.
        # 로컬 이미지를 data URI로 바꾸는 책임은 호출자(테스트 픽스처 포함)에게 있다.
        content += [
            {"type": "image_url", "image_url": {"url": image_url}}
            for image_url in source.image_urls
        ]

        if not content:
            raise ValueError("text_blocks와 image_urls가 모두 비어 있어 추출할 내용이 없습니다.")

        return [
            SystemMessage(content=_load_system_prompt()),
            HumanMessage(content=content),
        ]
