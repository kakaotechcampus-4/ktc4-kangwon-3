"""상품 원문에서 상품 정보·속성을 추출하는 에이전트."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ...prompts import PromptName, get_prompt
from ...schemas.agent import ExtractionInput
from ...schemas.product import Attribute, Product, ProductAttributes
from ..base import BaseAgent
from .errors import ExtractionFailedError
from .rules import detect_battery_capacity_conflict, extract_rule_based_attributes
from .seller_region import extract_seller_region

# 평가 러너 호환용. 러너가 공용 로더로 옮겨가면 제거 (#171 §3.2)
PROMPT_PATH = get_prompt(PromptName.EXTRACTION).path


class ExtractionAgent(BaseAgent[ExtractionInput, ProductAttributes, Product]):
    """상품 원문에서 상품 정보와 속성(툴 선택 신호)을 추출한다. 툴 선택·규제 판정은 안 함.

    모델 출력에 규칙 기반 추출(정규식)을 합쳐 Product를 만듦. 평가 호출은 usage_agent("extraction-eval")로 구분.
    """

    component_name = "extraction"
    prompt_name = PromptName.EXTRACTION
    output_schema = ProductAttributes
    error_class = ExtractionFailedError
    task_name = "상품 정보 추출"
    output_label = "상품"

    def _subject_id(self, input: ExtractionInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 상품 원문.

        Returns:
            str: 상품 ID.
        """
        return input.product_id

    def _build_messages(self, input: ExtractionInput) -> list[SystemMessage | HumanMessage]:
        """판매자 영역만 남긴 글과 이미지 URL로 모델 메시지를 만든다.

        이미지는 http(s) URL과 data URI를 같게 다룸 (로컬 이미지를 data URI로 바꾸는 건 호출자 몫).

        Args:
            input: 상품 원문.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.

        Raises:
            ValueError: 글과 이미지가 모두 비어 있는 경우.
        """
        source, _ = _trim_to_seller_region(input)
        content: list[dict[str, Any]] = [{"type": "text", "text": block} for block in source.text_blocks]
        content += [{"type": "image_url", "image_url": {"url": url}} for url in source.image_urls]
        # 글·이미지가 모두 비어 추출할 내용이 없음
        if not content:
            raise ValueError("text_blocks와 image_urls가 모두 비어 있어 추출할 내용이 없습니다.")
        return self._messages(content)

    def _finalize(self, output: ProductAttributes, input: ExtractionInput) -> Product:
        """모델 출력에 판매자 제목·규칙 추출 결과를 합쳐 Product를 만든다.

        규칙 추출은 모델과 독립으로 실행하고 결과만 합침. product_id·source_url은 요청 값 그대로.

        Args:
            output: 모델이 추출한 상품 속성.
            input: 상품 원문.

        Returns:
            Product: 추출 결과.
        """
        source, titles = _trim_to_seller_region(input)
        payload = output.model_dump()
        payload["listing_text"] = _keep_seller_titles(output.listing_text, titles)
        payload["attributes"] = _merge_attributes(output.attributes, extract_rule_based_attributes(source.text_blocks))
        payload["conflicts"] = _merge_conflicts(output.conflicts, detect_battery_capacity_conflict(source.text_blocks))
        return Product(product_id=source.product_id, source_url=source.source_url, **payload)


def _trim_to_seller_region(source: ExtractionInput) -> tuple[ExtractionInput, list[str]]:
    """쇼핑몰이 붙인 글(AI 요약·연관 상품·리뷰·검색창 등)을 잘라 판매자 영역만 남긴다 (#253).

    자르지 못한 블록은 원문 그대로라 이전보다 나빠지지 않음.

    Args:
        source: 상품 원문.

    Returns:
        tuple[ExtractionInput, list[str]]: 판매자 영역만 남긴 입력과 찾은 판매자 제목(중복 제거).
    """
    regions = [extract_seller_region(block) for block in source.text_blocks]
    trimmed = source.model_copy(update={"text_blocks": [region.text for region in regions]})
    titles = list(dict.fromkeys(region.title for region in regions if region.title))
    return trimmed, titles


def _keep_seller_titles(listing_text: list[str], titles: list[str]) -> list[str]:
    """판매자 제목 원문이 listing_text에 없으면 맨 앞에 넣는다 (#253 논의 ③).

    모델이 제목을 product_name으로만 옮기고 listing_text에서 빼는 경우가 있어(표시광고 검사가 읽는 곳) 코드가 넣음.

    Args:
        listing_text: 모델이 뽑은 판매 문구.
        titles: 판매자 영역에서 찾은 제목.

    Returns:
        list[str]: 빠진 제목을 앞에 붙인 판매 문구.
    """
    missing = [title for title in titles if not any(title in item for item in listing_text)]
    return missing + list(listing_text)


def _split_into_tokens(value: str) -> set[str]:
    """";"·","로 나열된 값을 소문자 토큰으로 쪼갠다. "CE-EMC(Electric)"는 괄호 앞 "ce-emc"도 넣음.

    Args:
        value: 속성 값.

    Returns:
        set[str]: 토큰 집합.
    """
    tokens: set[str] = set()
    for token in value.replace(",", ";").split(";"):
        token = token.strip().lower()
        if not token:
            continue
        tokens.add(token)
        paren_index = token.find("(")
        # 괄호 설명이 붙은 토큰 → 괄호 앞부분도 별도 토큰 (규칙이 뽑은 "CE-EMC"와 맞추려고)
        if paren_index != -1:
            tokens.add(token[:paren_index].strip())
    return tokens


def _merge_attributes(llm_attributes: list[Attribute], rule_attributes: list[Attribute]) -> list[Attribute]:
    """규칙 추출 속성 중 모델이 이미 뽑은 것(이름과 값 토큰이 둘 다 같음)을 빼고 덧붙인다.

    값만 비교하거나 부분 문자열로 비교하면 다른 항목의 같은 문자열 때문에 진짜 속성이 사라짐
    (예: "모델명: AC-220V-A1" 때문에 "전압 표기: 220V" 소실). 이름이 달라 생기는 중복은 허용 (소실보다 나음).

    Args:
        llm_attributes: 모델이 뽑은 속성.
        rule_attributes: 규칙이 뽑은 속성.

    Returns:
        list[Attribute]: 모델 속성 뒤에 새 규칙 속성을 붙인 목록.
    """
    merged = list(llm_attributes)
    existing_keys: set[tuple[str, str]] = set()
    for attribute in merged:
        name_key = attribute.name.strip().lower()
        existing_keys |= {(name_key, token) for token in _split_into_tokens(attribute.value)}

    for fact in rule_attributes:
        key = (fact.name.strip().lower(), fact.value.strip().lower())
        # 이름·값이 같은 속성이 아직 없을 때만 추가
        if key not in existing_keys:
            merged.append(fact)
            existing_keys.add(key)
    return merged


def _merge_conflicts(llm_conflicts: list[str], rule_conflicts: list[str]) -> list[str]:
    """모델과 규칙이 찾은 충돌 문장을 중복 없이 합친다.

    Args:
        llm_conflicts: 모델이 찾은 충돌.
        rule_conflicts: 규칙이 찾은 충돌.

    Returns:
        list[str]: 합친 충돌 목록. 모델 것이 먼저.
    """
    merged = list(llm_conflicts)
    for conflict in rule_conflicts:
        if conflict not in merged:
            merged.append(conflict)
    return merged
