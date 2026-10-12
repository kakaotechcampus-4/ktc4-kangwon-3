"""별표 원문을 파싱 에이전트 입력으로 다듬고, 큰 별표는 조각으로 나눔.

- compact_annex: 표 구조는 그대로 두고 빈칸·선 길이만 줄임
- split_annex: 표 단위로, 큰 표는 합친 칸이 모두 끝나는 가로선에서 나눔

원문 대조는 다듬기 전 원문으로 함. 다듬어도 테두리 문자·공백을 뺀 글자는 같음.
"""

import re
from dataclasses import dataclass

from .annex_check import source_labels

# 표 테두리 문자 (U+2500–257F)
_BOX_DRAWING = frozenset(chr(code) for code in range(0x2500, 0x2580))
# 가로선 문자. 길이만 의미 없어 한 글자로 줄임
_HORIZONTAL_RUN_RE = re.compile(r"([─━┄┅┈┉╌╍═])\1+")
# 칸을 채운 공백 (전각 공백 포함)
_SPACE_RUN_RE = re.compile(r"[ \t　]+")


def _is_border(line: str) -> bool:
    return all(char in _BOX_DRAWING or char == " " for char in line)


def compact_annex(content: str) -> str:
    """빈 줄을 지우고, 연속 공백을 하나로, 가로선 줄의 선 길이를 한 글자로 줄인다.

    가로선 줄의 교차 문자(┼ ┴ ┬ 등)와 선이 없는 칸 자리(공백)는 남김.
    세로로 합친 칸의 범위를 이 문자로 판단하기 때문.

    Args:
        content: 별표 원문.

    Returns:
        str: 다듬은 원문.
    """
    lines = []
    for line in content.splitlines():
        line = _SPACE_RUN_RE.sub(" ", line).strip()
        if not line:
            continue
        if _is_border(line):
            line = _HORIZONTAL_RUN_RE.sub(r"\1", line)
        lines.append(line)
    return "\n".join(lines)


# 조각 한도. 출력이 모델 출력 한도(mini 약 32k 토큰)를 넘지 않게 잡음
# 출력은 행마다 JSON 뼈대 약 110토큰 + 칸 글자라 행 수가 좌우. 입력은 작아도 행이 많으면 출력이 큼
# (운용요령 별표 2: 입력 약 6.7k 토큰, 183행 → 출력 약 28k 토큰 예상). 실측 후 조정
MAX_CHUNK_CHARS = 8_000
MAX_CHUNK_ROWS = 80
# 표 위·아래 테두리, 첫 칸부터 끝 칸까지 이어지는 가로선(합친 칸이 모두 끝나는 자리)의 첫 글자
_TABLE_TOP = frozenset("┌┍┎┏╒╓╔")
_TABLE_BOTTOM = frozenset("└┕┖┗╘╙╚")
_FULL_BORDER = frozenset("├┝┞┟┠┡┢╞╟╠")
# 머리글과 본문을 나누는 굵은 가로선
_HEADER_BORDER = frozenset("┝┡┢╞")
# 대분류 제목 (예: "1. 해상업무용 무선설비의 기기")
_HEADING_RE = re.compile(r"^\d+\.\s")


@dataclass(frozen=True)
class AnnexChunk:
    """에이전트에 한 번에 넣는 별표 조각.

    Attributes:
        content: 이 조각의 원문.
        context: 조각 앞에서 이어지는 별표 제목·대분류·표 머리글. 조각이 아니면 빈 문자열.
    """

    content: str
    context: str = ""


def _units(lines: list[str]) -> list[list[str]]:
    """앞 글줄과 그 뒤 표를 한 단위로 묶는다. 마지막 표 뒤 글줄(표 밖 비고 등)도 한 단위."""
    units: list[list[str]] = []
    current: list[str] = []
    in_table = False
    for line in lines:
        current.append(line)
        if line[0] in _TABLE_TOP:
            in_table = True
        elif in_table and line[0] in _TABLE_BOTTOM:
            in_table = False
            units.append(current)
            current = []
    if current:
        units.append(current)
    return units


@dataclass(frozen=True)
class _Limit:
    chars: int
    rows: int


def _size(lines: list[str]) -> int:
    return sum(len(line) + 1 for line in lines)


def _rows(lines: list[str]) -> int:
    return sum(source_labels("\n".join(lines)).values())


def _exceeds(lines: list[str], limit: _Limit) -> bool:
    return _size(lines) > limit.chars or _rows(lines) > limit.rows


def _pack(groups: list[list[str]], limit: _Limit) -> list[list[str]]:
    """줄 묶음을 순서대로 한도 안에 채운다. 한 묶음이 한도보다 크면 그대로 한 조각."""
    packs: list[list[str]] = []
    current: list[str] = []
    for group in groups:
        if current and _exceeds([*current, *group], limit):
            packs.append(current)
            current = []
        current = [*current, *group]
    if current:
        packs.append(current)
    return packs


def _split_unit(unit: list[str], limit: _Limit) -> list[tuple[list[str], list[str]]]:
    """큰 단위를 합친 칸이 모두 끝나는 가로선에서 나눈다.

    Returns:
        list[tuple[list[str], list[str]]]: (조각 줄, 대분류·표 머리글 줄). 첫 조각은 머리글을 본문에 포함.
    """
    top = next(index for index, line in enumerate(unit) if line[0] in _TABLE_TOP)
    header_end = next((index for index, line in enumerate(unit) if index > top and line[0] in _HEADER_BORDER),
                      next((index for index, line in enumerate(unit) if index > top and line[0] in _FULL_BORDER),
                           top))
    header = unit[:header_end + 1]
    groups: list[list[str]] = []
    for line in unit[header_end + 1:]:
        if line[0] in _FULL_BORDER or not groups:
            groups.append([])
        groups[-1].append(line)
    packs = _pack(groups, _Limit(chars=limit.chars - _size(header), rows=limit.rows))
    return [([*header, *packs[0]], [])] + [(pack, header) for pack in packs[1:]]


def split_annex(
    content: str,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    max_rows: int = MAX_CHUNK_ROWS,
) -> list[AnnexChunk]:
    """다듬은 별표를 글자 수·행 수 한도 안의 조각으로 나눈다. 작으면 조각 하나.

    대분류 제목과 그 표를 한 단위로 묶어 순서대로 채우고, 한 단위가 크면 표 안에서
    합친 칸이 모두 끝나는 가로선(첫 칸부터 이어지는 선)에서 나눔. 그 자리에서는 앞 행의
    분류가 이어지지 않아, 뒤 조각에는 별표 제목·대분류·표 머리글만 context로 붙임.
    그 가로선 사이 한 묶음이 한도보다 크면 나누지 않고 한 조각으로 둠.

    Args:
        content: compact_annex로 다듬은 별표.
        max_chars: 조각 하나의 최대 글자 수.
        max_rows: 조각 하나의 최대 품목 행 수 (원문 칸 머리 번호 수).

    Returns:
        list[AnnexChunk]: 원문 순서의 조각. 조각 content를 이으면 입력의 모든 줄이 한 번씩 나옴.
    """
    limit = _Limit(chars=max_chars, rows=max_rows)
    lines = content.splitlines()
    if not _exceeds(lines, limit):
        return [AnnexChunk(content=content)]

    units = _units(lines)
    # 별표 제목: 첫 단위에서 대분류 제목이나 표가 나오기 전까지
    first = units[0]
    title_end = next((index for index, line in enumerate(first)
                      if _HEADING_RE.match(line) or line[0] in _TABLE_TOP), len(first))
    title = first[:title_end]

    chunks: list[AnnexChunk] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(AnnexChunk(content="\n".join(current), context="\n".join(title) if chunks else ""))
            current = []

    for unit in units:
        if _exceeds(unit, limit) and any(line[0] in _TABLE_TOP for line in unit):
            flush()
            for part, header in _split_unit(unit, limit):
                # 첫 단위의 머리글 줄에는 별표 제목이 이미 들어 있음
                header = header[len(title):] if unit is first else header
                context = [*title, *header] if chunks else []
                chunks.append(AnnexChunk(content="\n".join(part), context="\n".join(context)))
            continue
        if current and _exceeds([*current, *unit], limit):
            flush()
        current.extend(unit)
    flush()
    return chunks
