"""별표 칸 글자를 품목 행 필드로 나누는 공통 규칙. 순수 함수만 둠.

- 한정·제외·포함 문구: 원문 글자를 자르기만 함(바꿔 쓰지 않음). 원문 대조(annex_check)가 글자 단위로 확인
- 번호: 분류(1.), 품목(가.), 세부품목(①) 머리 번호
"""

import re
from dataclasses import dataclass, field

from ...schemas.annex import AnnexAttribute

EXAMPLE_ATTRIBUTE = "예시 품목"

_SPACES_RE = re.compile(r"\s+")
# 줄 끝이 가운뎃점이면 다음 줄과 띄우지 않음 ("정보․통신․" + "사무기기")
_MIDDLE_DOTS = "·ㆍ․"
# "비고:", "비고 :", "비고)", 겹쳐 쓴 "비고) 비고)", 머리만 있는 "비고" 문단
_NOTE_RE = re.compile(r"^(비고\s*[:)]\s*)+|^비고\s*$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+")
_SENTENCE_END_RE = re.compile(r"(?<=다\.)\s+")
# "…에 한정하며, …는 제외한다."처럼 한 문장에 이어진 문구의 경계
_CLAUSE_END_RE = re.compile(r"(?<=며),\s*")
_EXCLUSION_RE = re.compile(r"제외(한다|하며|함|된다)?\.?$")
_INCLUSION_RE = re.compile(r"포함(한다|하며|함|된다)?\.?$")
# 품목 이름 끝 괄호가 한정·제외·포함 문구인지. "(…에 한정하며, … 본다)"처럼 중간에 있어도 됨
_QUALIFIER_RE = re.compile(r"(한정|제외|포함|해당)(한다|하며|함|된다|되며)|(한정|제외|포함|해당)$")
# "(전동식 커튼, 셔터, … 를 말한다)"처럼 문장으로 끝나는 괄호는 나열이 아닌 풀이
_SENTENCE_RE = re.compile(r"다\.?$")
_BRACKETS = {")": "(", "]": "["}
_AMENDMENT_RE = re.compile(r"\(\s*신\s*설\s*\)")
_DELETED_RE = re.compile(r"^<?삭\s*제")
_TITLE_RELATED_RE = re.compile(r"\s*\([^()]*관련\)\s*$")
# 제목 끝 표 이름: "(의) 세부품목", "의 종류 및 적용 안전기준"
_TITLE_TABLE_RE = re.compile(r"\s*(의\s*)?(세부\s*품목|종류\s*및\s*적용\s*안전기준)$")
_ANNEX_HEADING_RE = re.compile(r"^(■.*)?[\[【]별표")
# 괄호 안 항목이 이 수 이상이어야 나열로 봄. "(시스템 포함)" 같은 풀이 괄호는 그대로
_MIN_LISTED = 3


@dataclass
class Phrases:
    """한 행에 붙는 한정·제외·포함 문구 묶음.

    Attributes:
        conditions: 한정 문구.
        exclusions: 제외 문구.
        inclusions: 포함 문구.
    """

    conditions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    inclusions: list[str] = field(default_factory=list)

    def extend(self, conditions: list[str], exclusions: list[str], inclusions: list[str]) -> None:
        """문구를 뒤에 붙인다."""
        self.conditions.extend(conditions)
        self.exclusions.extend(exclusions)
        self.inclusions.extend(inclusions)

    def merged(self, *others: "Phrases | None") -> "Phrases":
        """이 묶음 뒤에 다른 묶음들을 이어 붙인 새 묶음."""
        result = Phrases(list(self.conditions), list(self.exclusions), list(self.inclusions))
        for other in others:
            if other is not None:
                result.extend(other.conditions, other.exclusions, other.inclusions)
        return result


def join_lines(text: str) -> str:
    """칸 안 여러 줄을 한 줄로 잇는다. 바로 앞 줄과 같은 줄(병합 칸에 되풀이된 분류)은 뺌."""
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    joined = ""
    for line in lines:
        joined += line if not joined or joined[-1] in _MIDDLE_DOTS else " " + line
    return _SPACES_RE.sub(" ", joined)


def is_note(text: str) -> bool:
    """비고 칸인지."""
    return bool(_NOTE_RE.match(text.strip()))


def is_deleted(text: str) -> bool:
    """삭제 표시(삭제<2023. 3. 20.>, <삭제>)인지."""
    return bool(_DELETED_RE.match(text.strip()))


def is_no_target(text: str) -> bool:
    """대상 없음 칸인지."""
    return "".join(text.split()) == "대상없음"


def note_entries(text: str) -> list[str]:
    """비고 칸을 번호 항목마다 하나로 나눈다. 항목 안 줄바꿈은 이음. 머리 "비고:"와 번호는 뺌.

    Args:
        text: 비고 칸 글자.

    Returns:
        list[str]: 비고 항목 목록.
    """
    entries: list[str] = []
    lines = text.strip().splitlines()
    if lines:
        lines[0] = _NOTE_RE.sub("", lines[0])
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _NUMBERED_RE.match(line) or not entries:
            entries.append(_NUMBERED_RE.sub("", line))
        else:
            entries[-1] = f"{entries[-1]} {line}"
    return [_SPACES_RE.sub(" ", entry).strip() for entry in entries]


def classify_phrases(text: str) -> tuple[list[str], list[str], list[str]]:
    """문구를 문장·"며," 경계에서 잘라 한정·제외·포함으로 나눈다.

    제외·포함으로 끝나지 않는 문구(한정, 해당, 그 밖의 설명)는 한정으로 둠.

    Args:
        text: 비고 칸 글자 또는 괄호 안 문구.

    Returns:
        tuple[list[str], list[str], list[str]]: (한정, 제외, 포함) 문구.
    """
    conditions: list[str] = []
    exclusions: list[str] = []
    inclusions: list[str] = []
    for entry in note_entries(text):
        for sentence in _SENTENCE_END_RE.split(entry):
            for clause in _CLAUSE_END_RE.split(sentence):
                clause = clause.strip()
                if not clause:
                    continue
                if _EXCLUSION_RE.search(clause):
                    exclusions.append(clause)
                elif _INCLUSION_RE.search(clause):
                    inclusions.append(clause)
                else:
                    conditions.append(clause)
    return conditions, exclusions, inclusions


def _trailing_bracket(text: str) -> tuple[str, str] | None:
    """끝 괄호를 (괄호 앞, 괄호 안)으로 나눈다. 끝이 괄호가 아니면 None."""
    if not text or text[-1] not in _BRACKETS:
        return None
    close, depth = text[-1], 0
    for index in range(len(text) - 1, -1, -1):
        depth += text[index] == close
        depth -= text[index] == _BRACKETS[close]
        if depth == 0:
            return text[:index].strip(), text[index + 1:-1].strip()
    return None


def split_qualifier(text: str) -> tuple[str, list[str], list[str], list[str]]:
    """이름 끝 괄호의 한정·제외·포함 문구를 떼어 낸다. 그 밖의 괄호("(착용형)")는 이름에 둠.

    Args:
        text: 번호를 뺀 품목·분류 이름 (예: "절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)").

    Returns:
        tuple[str, list[str], list[str], list[str]]: (이름, 한정, 제외, 포함).
    """
    text = _SPACES_RE.sub(" ", _AMENDMENT_RE.sub("", text)).strip()
    parsed = _trailing_bracket(text)
    if parsed is None or not parsed[0] or not _QUALIFIER_RE.search(parsed[1]):
        return text, [], [], []
    return parsed[0], *classify_phrases(parsed[1])


def _split_top_level(text: str) -> list[str]:
    """괄호 밖 쉼표에서만 나눈다. 앞 "- "와 끝 " 등"은 뺌. "형광등"처럼 붙어 쓴 등은 이름이라 둠."""
    parts, depth, current = [], 0, ""
    for char in text:
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    cleaned = (part.strip().removeprefix("- ").strip().removesuffix(" 등").strip() for part in parts)
    return [part for part in cleaned if part]


def split_examples(name: str) -> tuple[str, list[AnnexAttribute]]:
    """이름 끝 괄호가 품목 나열이면 이름은 앞부분만 남기고 나열을 예시 품목 칸으로 옮긴다.

    Args:
        name: 품목 이름 (예: "투영기(슬라이드 투영기, OHP, 필름 투영기)").

    Returns:
        tuple[str, list[AnnexAttribute]]: (이름, 예시 품목 칸). 나열이 아니면 (이름 그대로, []).
    """
    parsed = _trailing_bracket(name)
    if parsed is None:
        return name, []
    head, inner = parsed
    examples = _split_top_level(inner)
    if not head or len(examples) < _MIN_LISTED or _SENTENCE_RE.search(inner):
        return name, []
    return head, [AnnexAttribute(name=EXAMPLE_ATTRIBUTE, values=examples)]


def scheme_from_title(title: str) -> str:
    """별표 제목에서 규제 구분을 뗀다. 관련 조문 괄호와 끝 "(의) 세부품목"은 뺌.

    Args:
        title: 별표 제목 (예: "안전인증대상전기용품 세부품목(제3조 관련)").

    Returns:
        str: 규제 구분 (예: "안전인증대상전기용품").
    """
    return _TITLE_TABLE_RE.sub("", _TITLE_RELATED_RE.sub("", title.strip())).strip()


def find_title(paragraphs: list[str]) -> str | None:
    """표 앞 문단 중 별표 머리("[별표 4]", "■ … [별표 3]")가 아닌 마지막 문단을 제목으로 본다."""
    titles = [paragraph for paragraph in paragraphs if not _ANNEX_HEADING_RE.match(paragraph)]
    return titles[-1] if titles else None
