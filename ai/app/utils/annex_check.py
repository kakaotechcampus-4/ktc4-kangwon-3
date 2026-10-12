"""별표 파싱 결과를 원문과 대조. 모델 없이 도는 순수 함수만 둠.

- 문구 대조: 품목명·분류·비고·source_text가 원문에 그대로 있는지
- 번호 대조: 원문 칸 머리의 품목 번호가 items·skipped에 빠짐없이 있는지
"""

import re
from collections import Counter

from ..schemas.agents.annex import AnnexParseOutput

# 표 테두리 문자 (U+2500–257F)
_BOX_DRAWING = {code: None for code in range(0x2500, 0x2580)}
# 칸을 나누는 세로선
_CELL_SPLIT_RE = re.compile(r"[│┃┆┇┊┋║]")
# 칸 머리 번호: ①~⑳, 깨진 원문자(뒤에 공백이 오는 ?), 1)
# "?단말장치"처럼 공백 없이 글자가 이어지는 ?는 번호가 아니라 깨진 특수문자
# "12)~16) : 주방가전"은 범위 안내라 제외
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_LABEL_RE = re.compile(rf"^\?*\s*([{_CIRCLED}])|^(\?)(?=\s|$)|^(\d+\))(?!\s*~)")


def normalize(text: str) -> str:
    """테두리 문자와 공백을 지운다. 줄바꿈·칸 나눔 위치가 달라도 같은 글자로 비교하기 위함."""
    return "".join(text.translate(_BOX_DRAWING).split())


def _haystacks(content: str) -> list[str]:
    """대조 대상 문자열. 원문 전체와, 같은 칸 순서끼리 줄을 이어 붙인 열 문자열들.

    여러 줄에 걸친 칸은 줄마다 다른 칸 글자가 끼어 원문 전체에서는 이어지지 않음.
    """
    columns: dict[int, list[str]] = {}
    for line in content.splitlines():
        for index, cell in enumerate(_CELL_SPLIT_RE.split(line)):
            columns.setdefault(index, []).append(cell)
    return [normalize(content), *(normalize("".join(cells)) for cells in columns.values())]


def _pattern(needle: str) -> re.Pattern:
    """원문의 ?(깨진 글자)와 출력의 ?를 모두 아무 글자 하나로 보는 패턴."""
    parts = [r"." if char == "?" else rf"(?:{re.escape(char)}|\?)" for char in needle]
    return re.compile("".join(parts))


def contains(haystacks: list[str], text: str) -> bool:
    """문구가 대조 대상 중 하나에 그대로 있는지. 빈 문구는 실패."""
    needle = normalize(text)
    if not needle:
        return False
    pattern = _pattern(needle)
    return any(pattern.search(haystack) for haystack in haystacks)


def _label(text: str) -> str | None:
    """칸 머리 또는 item_label에서 대조할 번호를 꺼낸다. 대상 아닌 번호(가., 1.)는 None."""
    match = _LABEL_RE.match(text.strip())
    if match is None:
        return None
    return next(group for group in match.groups() if group)


def source_labels(content: str) -> Counter:
    """원문 칸 머리의 품목 번호 개수.

    같은 줄의 같은 번호는 한 번만 셈. 품목·세부품목 칸에 같은 번호가 나란히 붙은 표가 있음
    (예: 운용요령 별표 3의2 "① 재사용전지모듈 │① 재사용전지모듈").
    """
    counts: Counter = Counter()
    for line in content.splitlines():
        labels = {_label(cell) for cell in _CELL_SPLIT_RE.split(line)}
        counts.update(label for label in labels if label)
    return counts


def output_labels(output: AnnexParseOutput) -> Counter:
    """출력 items·skipped의 품목 번호 개수."""
    labels = [row.item_label for row in (*output.items, *output.skipped) if row.item_label]
    return Counter(label for label in map(_label, labels) if label)


def check_annex(content: str, output: AnnexParseOutput) -> list[str]:
    """파싱 결과를 원문과 대조해 실패 사유를 돌려준다. 빈 목록이면 통과.

    attributes는 ○ 행렬 열 이름을 이어 붙인 값이라 원문 대조하지 않음.

    Args:
        content: 별표 원문 전체.
        output: 에이전트 출력 (조각이면 병합 후).

    Returns:
        list[str]: 실패 사유. 원문에 없는 문구, 빠지거나 남는 번호, 중복 행.
    """
    haystacks = _haystacks(content)
    reasons: list[str] = []

    def check(where: str, text: str) -> None:
        if not contains(haystacks, text):
            reasons.append(f"{where}: 원문에 없는 문구 {text!r}")

    check("scheme", output.scheme)
    seen: set[tuple] = set()
    for index, item in enumerate(output.items):
        where = f"items[{index}] {item.item_label or ''} {item.item_name}".strip()
        key = (tuple(item.category_path), item.item_label, item.item_name)
        if key in seen:
            reasons.append(f"{where}: 중복 행")
        seen.add(key)
        check(where, item.item_name)
        check(where, item.source_text)
        for text in (*item.category_path, *item.conditions, *item.exclusions, *item.inclusions):
            check(where, text)
    for index, row in enumerate(output.skipped):
        check(f"skipped[{index}] {row.item_label or ''}".strip(), row.reason)
    for index, note in enumerate(output.notes):
        check(f"notes[{index}]", note)

    expected, actual = source_labels(content), output_labels(output)
    if missing := expected - actual:
        reasons.append(f"번호 누락: {dict(missing)}")
    if extra := actual - expected:
        reasons.append(f"원문보다 많은 번호: {dict(extra)}")
    return reasons
