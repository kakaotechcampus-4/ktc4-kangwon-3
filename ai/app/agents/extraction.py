"""추출 담당자가 구현하는 에이전트."""

from typing import Any

from ..schemas.agent import ExtractionInput
from ..schemas.product import Attribute, ProductAttributes, Product
from ..utils.extraction_rules import detect_battery_capacity_conflict, extract_rule_based_attributes
from .base import AgentError, AgentSpec, BaseAgent


class ExtractionFailedError(AgentError):
    """LLM 호출 또는 구조화 출력 파싱이 실패했을 때 발생한다.

    레이트리밋·인증 오류·스키마 불일치 등 원인은 다양하지만, 호출부(파이프라인)는
    langchain·openai SDK의 세부 예외 타입을 알 필요 없이 이 하나만 잡으면 된다.
    원인 예외는 ``raise ... from exc``로 보존해 traceback에서 근본 원인을 확인할 수 있다.
    """


class ExtractionAgent(BaseAgent[ProductAttributes]):
    """상품 원문에서 정보를 추출한다. 툴 선택이나 규제 판정은 맡지 않는다."""

    spec = AgentSpec(
        name="extraction",
        prompt="extraction",
        output=ProductAttributes,
        error=ExtractionFailedError,
        call_failed_message="상품 정보 추출에 실패했습니다: {exc}",
        parse_failed_message="모델 응답이 상품 스키마와 맞지 않습니다: {error}",
    )

    def extract(self, source: ExtractionInput) -> Product:
        """
        입력: 수집된 상품 텍스트·이미지 참조
        출력: 상품 정보와 15개 상품 속성(6개 심사 툴 선택에 참고할 신호)을 담은 Product

        raises ExtractionFailedError: LLM 호출·구조화 출력 파싱이 실패한 경우.
            text_blocks·image_urls가 모두 비어 입력 자체가 없는 경우는 ValueError.
        """
        fields = self._invoke(self._user_content(source), subject_id=source.product_id)

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

    @staticmethod
    def _user_content(source: ExtractionInput) -> list[dict[str, Any]]:
        """원문 텍스트·이미지를 멀티모달 사용자 입력 블록으로 만든다.

        Args:
            source: 수집된 상품 텍스트·이미지 참조.

        Returns:
            list[dict[str, Any]]: text / image_url 블록 목록.

        Raises:
            ValueError: text_blocks와 image_urls가 모두 비어 있는 경우 (모델 호출 전).
        """
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

        return content


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
    # 항목 이름과 값이 **둘 다** 같을 때만 중복으로 본다.
    # (예: LLM이 "인증정보: CE-RoHS; CE-EMC(Electric)"를 이미 뽑았으면 규칙의 인증정보
    # "CE-RoHS"·"CE-EMC"는 둘 다 이미 있는 값으로 인식해서 또 안 넣는다)
    #
    # 값만 비교하면 안 된다. LLM이 "모델명: 220V"처럼 전혀 다른 항목에 같은 문자열을
    # 담아뒀다는 이유만으로 규칙이 찾은 진짜 "정격전압: 220V"가 통째로 사라진다.
    # 부분 문자열 비교를 안 쓰는 이유도 같다 — "220V"가 "AC-220V-A1"(모델번호)의
    # 부분 문자열이라는 이유로 정격전압 항목이 버려지면 안 된다.
    #
    # 이름이 다르면 중복이 남을 수는 있다(LLM이 "인증"이라 쓰고 규칙은 "인증정보"인 경우).
    # 그건 하위 에이전트가 같은 값을 두 번 보는 것뿐이라 판단이 틀어지지 않는 반면,
    # 소실은 조용히 근거가 사라지는 것이라 훨씬 비싸다. 소실보다 중복을 택한다.
    merged = list(llm_attributes)
    existing_keys: set[tuple[str, str]] = set()
    for attribute in merged:
        name_key = attribute.name.strip().lower()
        existing_keys |= {(name_key, token) for token in _split_into_tokens(attribute.value)}

    for fact in rule_attributes:
        key = (fact.name.strip().lower(), fact.value.strip().lower())
        if key not in existing_keys:
            merged.append(fact)
            existing_keys.add(key)
    return merged


def _merge_conflicts(llm_conflicts: list[str], rule_conflicts: list[str]) -> list[str]:
    merged = list(llm_conflicts)
    for conflict in rule_conflicts:
        if conflict not in merged:
            merged.append(conflict)
    return merged
