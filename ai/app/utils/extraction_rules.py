"""정규식으로 확정 가능한 사실만 뽑는 규칙 기반 사전추출.

LLM 판단이 필요한 문맥 해석(무선통신 vs 무선충전 구분, 어린이 대상 여부 등)은 다루지 않는다.
여기서 다루는 건 "패턴만 봐도 틀릴 수 없는" 값(인증코드, 전압, 용량, 주파수)뿐이다.
LLM과 완전히 독립적으로 실행되며, 결과는 ExtractionAgent가 LLM 출력과 합친다
("규칙은 규칙, AI는 AI" — 정규식이 실패해도 LLM 판단을 오염시키지 않는다).
공용 유틸로 두어 다른 에이전트(예: 검증 단계에서 인증번호 형식 재확인)에서도 쓸 수 있다.
"""

import re

from ..schemas.product import Attribute

# 단어 경계에 \b를 쓰지 않는다. 파이썬의 \b는 한글도 단어 문자로 보기 때문에 "CE인증",
# "220V정격"처럼 한글이 바로 붙은(한국어 페이지에서 아주 흔한) 표기를 놓친다.
# 대신 "앞뒤에 영문자가 아닐 것"만 요구해서 영단어 안의 우연한 일치(PRICE의 CE)는 막고
# 한글·숫자·기호가 붙은 경우는 잡는다.
_NOT_LETTER_BEFORE = r"(?<![A-Za-z])"
_NOT_LETTER_AFTER = r"(?![A-Za-z])"
_NOT_ALNUM_BEFORE = r"(?<![A-Za-z0-9])"
_NOT_ALNUM_AFTER = r"(?![A-Za-z0-9])"

# 인증 마크: CE-RoHS, CE-EMC, KC, FCC, CPC 등. 대문자 약어 + 선택적 하이픈-키워드.
# 마크 이름만 알려주며, 실제 검증에 쓰는 "번호"는 아래 두 패턴이 따로 잡는다.
_CERT_MARK_PATTERN = re.compile(
    _NOT_LETTER_BEFORE + r"(?:CE|KC|FCC|RoHS|CPC)(?:-[A-Za-z]+)?" + _NOT_LETTER_AFTER
)
# KC 안전인증·안전확인 번호(국가기술표준원, 1-3-1 조회 키). 예: XU101234-19001, HH07107-13001,
# 어린이제품 CB061R0069-3002. 발급 시기에 따라 자릿수가 조금씩 달라 범위로 잡는다.
_KC_CERT_NUMBER_PATTERN = re.compile(
    _NOT_ALNUM_BEFORE
    + r"(?:[A-Z]{2}\d{5,6}-\d{4,5}[A-Z]?|[A-Z]{2}\d{3}[A-Z]\d{4}-\d{4})"
    + _NOT_ALNUM_AFTER
)
# 전파 적합성평가 번호(국립전파연구원, 1-4 조회 키). 2019년 이후 R-R-xxx-yyyy 형식과
# 그 이전 KCC-REM-xxx-yyyy / MSIP-CRM-xxx-yyyy 형식을 모두 잡는다.
_RADIO_CERT_NUMBER_PATTERN = re.compile(
    _NOT_ALNUM_BEFORE
    + r"(?:R-[A-Z]{1,3}-[A-Za-z0-9]{2,}-[A-Za-z0-9._-]+"
    + r"|(?:KCC|MSIP|MSIT)-[A-Z]{3}-[A-Za-z0-9]+-[A-Za-z0-9._-]+)"
    + _NOT_ALNUM_AFTER
)
# 정격전압: "220V", "36V 이하", "220V정격"
_VOLTAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*V" + _NOT_LETTER_AFTER)
# 배터리 용량: "1460mAh", "1460mAh케이스"
_CAPACITY_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*mAh" + _NOT_LETTER_AFTER, re.IGNORECASE)
# 통신 주파수: "2.4GHz", "900MHz"
_FREQUENCY_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:GHz|MHz)" + _NOT_LETTER_AFTER, re.IGNORECASE)

# "배터리 미포함" 류 부정 표현. 완벽한 자연어 이해가 아니라 실제로 관찰된 패턴(파워뱅크
# 테스트 케이스) 하나만 다룬다. 다른 표현("전자 부품 미포함" 등)은 잡지 못할 수 있다.
_NO_BATTERY_PATTERN = re.compile(r"(?:배터리|전지).{0,10}미포함")

_PATTERNS_BY_NAME = (
    (_KC_CERT_NUMBER_PATTERN, "KC 인증번호"),
    (_RADIO_CERT_NUMBER_PATTERN, "전파 인증번호"),
    (_CERT_MARK_PATTERN, "인증정보"),
    (_VOLTAGE_PATTERN, "정격전압"),
    (_CAPACITY_PATTERN, "배터리 용량"),
    (_FREQUENCY_PATTERN, "통신 주파수"),
)


def extract_rule_based_attributes(text_blocks: list[str]) -> list[Attribute]:
    """정규식으로 뽑히는 확정적 사실을 Attribute 목록으로 반환한다. 못 찾으면 빈 리스트."""
    facts: list[Attribute] = []
    for block in text_blocks:
        for pattern, name in _PATTERNS_BY_NAME:
            for match in pattern.finditer(block):
                facts.append(
                    Attribute(name=name, value=match.group(0), source_text=_context(block, match))
                )
    return facts


def detect_battery_capacity_conflict(text_blocks: list[str]) -> list[str]:
    """배터리 용량(mAh) 표기와 '배터리 미포함' 문구가 같은 상세페이지에 함께 있는
    경우처럼, 정규식만으로 판단 가능한 모순 하나를 감지한다.

    다른 종류의 모순(카테고리는 "디퓨저"인데 속성은 "무향"인 경우 등)은 부정 표현이
    없어서 정규식으로 못 잡는다 — 이건 여전히 LLM이 conflicts 필드로 직접 보고해야 한다.
    """
    # 실제 케이스(파워뱅크)에서 용량은 제목 블록에, "미포함" 문구는 스펙표 블록에 따로
    # 있었다. 블록 단위가 아니라 전체 상세페이지를 합쳐서 봐야 이런 경우를 잡는다.
    combined = "\n".join(text_blocks)
    # 같은 페이지에 같은 스펙이 여러 번 반복되기도 해서(대소문자 표기까지 제각각),
    # 표시용 메시지에는 중복 없이 대표값만 남긴다. 원문 순서는 유지한다.
    seen: set[str] = set()
    capacities: list[str] = []
    for match in _CAPACITY_PATTERN.findall(combined):
        key = match.lower()
        if key not in seen:
            seen.add(key)
            capacities.append(match)

    if capacities and _NO_BATTERY_PATTERN.search(combined):
        return [
            f"배터리 용량 표기({', '.join(capacities)})가 있으나 "
            "같은 상세페이지에 '배터리 미포함'이라는 문구도 있어 모순됩니다."
        ]
    return []


def _context(block: str, match: re.Match) -> str:
    """매치 주변 문맥을 짧게 잘라 근거로 남긴다."""
    start = max(0, match.start() - 20)
    end = min(len(block), match.end() + 20)
    return block[start:end].strip()
