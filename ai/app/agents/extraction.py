"""추출 담당자가 구현하는 에이전트."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import build_chat_model
from ..schemas.agent import ExtractionInput
from ..schemas.product import Attribute, ProductAttributes, Product
from ..utils.extraction_rules import detect_battery_capacity_conflict, extract_rule_based_attributes

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extraction.md"

logger = logging.getLogger(__name__)


class ExtractionFailedError(RuntimeError):
    """LLM 호출 또는 구조화 출력 파싱이 실패했을 때 발생한다.

    레이트리밋·인증 오류·스키마 불일치 등 원인은 다양하지만, 호출부(파이프라인)는
    langchain·openai SDK의 세부 예외 타입을 알 필요 없이 이 하나만 잡으면 된다.
    원인 예외는 ``raise ... from exc``로 보존해 traceback에서 근본 원인을 확인할 수 있다.
    """


class _StructuredExtractor(Protocol):
    """``model.with_structured_output(..., include_raw=True)``가 돌려주는 결과물의 최소 인터페이스.

    invoke()는 ``{"raw": AIMessage, "parsed": ProductAttributes | None, "parsing_error": Exception | None}``
    형태의 dict를 돌려준다. raw에서 토큰 사용량을 읽기 위해 include_raw를 켠다.
    """

    def invoke(self, messages: list) -> dict[str, Any]: ...


class _ModelLike(Protocol):
    """ExtractionAgent가 실제로 쓰는 메서드만 좁혀 놓은 타입.

    ``BaseChatModel``은 이 구조를 만족하므로 실제 모델도 그대로 넘길 수 있고,
    테스트에서는 ``BaseChatModel``을 상속하지 않는 가벼운 스텁도 그대로 넘길 수 있다.
    """

    def with_structured_output(self, schema: type[ProductAttributes]) -> _StructuredExtractor: ...


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    # extract() 호출마다 디스크를 다시 읽지 않도록 캐싱한다. 프롬프트 파일은 배포 중 안 바뀐다.
    return _PROMPT_PATH.read_text(encoding="utf-8")


class ExtractionAgent:
    """상품 원문에서 정보를 추출한다. 툴 선택이나 규제 판정은 맡지 않는다."""

    def __init__(self, model: _ModelLike | None = None) -> None:
        # 모델 생성은 config.build_chat_model()에 맡긴다. 에이전트마다 ChatOpenAI를 직접
        # 만들면 base_url·허용 모델·타임아웃 설정이 흩어지고, base_url이 비었을 때
        # OpenAI 공식 서버로 요청이 나가 원인을 알기 어려운 401을 만난다.
        # model을 주입하면 테스트에서 실제 API 호출 없이 검증할 수 있다.
        # include_raw=True: 파싱 결과와 함께 원본 응답을 받아 토큰 사용량(캐시 적용 여부 포함)을
        # 기록한다. 측정이 없으면 토큰 최적화도 할 수 없다.
        self._structured_model = (model or build_chat_model()).with_structured_output(
            ProductAttributes, include_raw=True
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
            result = self._structured_model.invoke(messages)
        except Exception as exc:
            # langchain·openai SDK의 구체적인 예외 타입(레이트리밋·인증 오류 등)을
            # 호출부가 몰라도 되게 하나로 감싼다. 여기서 삼키지 않고 원인은 그대로 보존한다.
            raise ExtractionFailedError(f"상품 정보 추출에 실패했습니다: {exc}") from exc

        # include_raw=True면 스키마 불일치는 예외가 아니라 parsing_error로 돌아온다.
        parsing_error = result.get("parsing_error")
        fields = result.get("parsed")
        if parsing_error is not None or fields is None:
            raise ExtractionFailedError(
                f"모델 응답이 상품 스키마와 맞지 않습니다: {parsing_error}"
            ) from parsing_error

        _log_token_usage(result.get("raw"))

        # 규칙 기반 사전추출: LLM 호출과 완전히 독립적으로 실행하고 결과만 합친다
        # ("규칙은 규칙, AI는 AI" — 정규식이 하나도 안 걸려도 LLM 판단엔 영향 없음).
        rule_attributes = extract_rule_based_attributes(source.text_blocks)
        rule_conflicts = detect_battery_capacity_conflict(source.text_blocks)

        payload = fields.model_dump()
        payload["attributes"] = _merge_attributes(fields.attributes, rule_attributes)
        payload["conflicts"] = _merge_conflicts(fields.conflicts, rule_conflicts)

        # product_id·source_url은 모델이 만들지 않는다. 요청 값을 그대로 옮긴다.
        return Product(
            product_id=source.product_id,
            source_url=source.source_url,
            **payload,
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


def _log_token_usage(raw_message: Any) -> None:
    # 고정 prefix(시스템 프롬프트+스키마 ≈ 2,250토큰)가 캐시되면 cache_read에 잡힌다.
    # 이 값이 계속 0이면 프롬프트 캐시가 안 먹는 것이므로 prefix가 호출마다 달라지는지 봐야 한다.
    usage = getattr(raw_message, "usage_metadata", None)
    if not usage:
        return
    input_details = usage.get("input_token_details") or {}
    logger.info(
        "추출 토큰 사용량 input=%s (cache_read=%s) output=%s total=%s",
        usage.get("input_tokens"),
        input_details.get("cache_read"),
        usage.get("output_tokens"),
        usage.get("total_tokens"),
    )
    # 게이트웨이(엘리스 MLAPI)가 주는 원본 필드명은 OpenAI와 다를 수 있어 디버그로 남긴다.
    response_metadata = getattr(raw_message, "response_metadata", None) or {}
    if response_metadata.get("token_usage"):
        logger.debug("게이트웨이 원본 usage: %s", response_metadata["token_usage"])


def _split_into_tokens(value: str) -> set[str]:
    # ";"/","로 나열된 값을 토큰으로 쪼갠다. "CE-EMC(Electric)"처럼 괄호 설명이 붙은
    # 토큰은 괄호 앞부분도 별도로 넣어서, 규칙이 뽑은 "CE-EMC"와도 정확히 매칭되게 한다.
    tokens: set[str] = set()
    for token in value.replace(",", ";").split(";"):
        token = token.strip().lower()
        if not token:
            continue
        tokens.add(token)
        paren_index = token.find("(")
        if paren_index != -1:
            tokens.add(token[:paren_index].strip())
    return tokens


def _merge_attributes(
    llm_attributes: list[Attribute], rule_attributes: list[Attribute]
) -> list[Attribute]:
    # LLM이 이미 뽑은 값과 정확히(또는 괄호 설명을 뗀 뒤 정확히) 같을 때만 중복으로 본다.
    # (예: LLM이 "인증정보: CE-RoHS; CE-EMC(Electric)"를 이미 뽑았으면 규칙의 "CE-RoHS"·"CE-EMC"는
    # 둘 다 이미 있는 값으로 인식해서 또 안 넣는다)
    # 부분 문자열 비교는 쓰지 않는다 — "220V"가 전혀 다른 속성값 "AC-220V-A1"(모델번호 등)의
    # 부분 문자열이라는 이유만으로 진짜 정격전압 항목이 통째로 버려지는 사고가 날 수 있다.
    merged = list(llm_attributes)
    existing_tokens: set[str] = set()
    for attribute in merged:
        existing_tokens |= _split_into_tokens(attribute.value)

    for fact in rule_attributes:
        fact_value = fact.value.strip().lower()
        if fact_value not in existing_tokens:
            merged.append(fact)
            existing_tokens.add(fact_value)
    return merged


def _merge_conflicts(llm_conflicts: list[str], rule_conflicts: list[str]) -> list[str]:
    merged = list(llm_conflicts)
    for conflict in rule_conflicts:
        if conflict not in merged:
            merged.append(conflict)
    return merged
