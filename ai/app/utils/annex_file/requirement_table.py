"""대상법령·구비요건 표(관세법 제226조 세관장확인물품 고시 별표 1·2)를 품목 행으로 푼다. 순수 함수만 둠.

표 모양
    - 머리 행 "대상법령 및 물품의 범위 | 구비요건"이 쪽마다 되풀이되며 표가 여러 개로 끊김
    - "(N)「법률」해당 물품" 행: 구비요건이 있으면 품목, 비어 있으면 아래 "(가)" 행들의 분류
    - "(N)「법률」… ⏎ (가)…"처럼 한 칸에 둘 다 있으면 (가)가 품목, (N)이 분류
    - 구비요건 칸은 병합으로 여러 품목에 걸치기도 함. "ㅇ" 줄마다 값 하나
    - 표 뒤 "나. 물품별 수출요건" 아래 문단: 표 전체 비고
"""

import re

from ...schemas.annex import AnnexAttribute, AnnexItem, AnnexParseOutput, AnnexSkippedRow
from .grid import Block, Cell, Table
from .text import split_qualifier

HEADER = ("대상법령및물품의범위", "구비요건")
REQUIREMENT_ATTRIBUTE = "구비요건"

_LAW_RE = re.compile(r"^(\(\d+\))\s*(.*)$")
_SUB_RE = re.compile(r"^(\([가-힣]\))\s*(.*)$")
# "(삭제)", "< 삭 제 >", "<삭제>"
_DELETED_RE = re.compile(r"^[(<\s]*삭\s*제[)>\s]*$")
_ANNEX_PREFIX_RE = re.compile(r"^[\[【]별표[^\]】]*[\]】]\s*")
_SECTION_HEADING_RE = re.compile(r"^[가-힣]\.\s")
_REQUIREMENT_BULLET_RE = re.compile(r"^ㅇ\s*")
_NOTE_DELETED_RE = re.compile(r"^\S+\s*<\s*삭\s*제\s*>$")


def is_requirement_table(table: Table) -> bool:
    """머리 행이 대상법령 및 물품의 범위·구비요건인 2칸 표인지."""
    if table.col_count != len(HEADER) or table.row_count < 1:
        return False
    return tuple("".join(cell.text.split()) if cell else "" for cell in table.grid()[0]) == HEADER


def parse_requirement_tables(blocks: list[Block]) -> AnnexParseOutput:
    """대상법령·구비요건 표들로 이루어진 별표를 품목 행으로 푼다.

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과).

    Returns:
        AnnexParseOutput: 품목 행(구비요건은 추가 칸), 뺀 행(삭제), 표 뒤 문단의 비고.

    Raises:
        ValueError: 대상법령·구비요건 표가 없거나 제목 문단이 없는 경우.
    """
    tables = [block for block in blocks if isinstance(block, Table)]
    if not tables or not all(is_requirement_table(table) for table in tables):
        raise ValueError("대상법령·구비요건 표로 이루어진 별표가 아닙니다.")
    paragraphs = [block for block in blocks[:blocks.index(tables[0])] if isinstance(block, str)]
    if not paragraphs:
        raise ValueError("별표 제목 문단이 없습니다.")
    scheme = _ANNEX_PREFIX_RE.sub("", paragraphs[0]).strip()

    items: list[AnnexItem] = []
    skipped: list[AnnexSkippedRow] = []
    law: str | None = None
    for table in tables:
        for target, requirement in table.grid()[1:]:
            if target is None or not target.text.strip():
                continue
            law = _add_row(target, requirement, law, items, skipped)

    after = [block for block in blocks[blocks.index(tables[-1]) + 1:] if isinstance(block, str)]
    notes = [text for text in after if not _SECTION_HEADING_RE.match(text) and not _NOTE_DELETED_RE.match(text)]
    return AnnexParseOutput(scheme=scheme, items=items, skipped=skipped, notes=notes)


def _add_row(target: Cell, requirement: Cell | None, law: str | None, items: list[AnnexItem],
             skipped: list[AnnexSkippedRow]) -> str | None:
    """행 하나를 품목·뺀 행으로 옮기고, 아래 "(가)" 행들이 쓸 현재 법률 분류를 돌려준다."""
    lines = [line.strip() for line in target.text.splitlines() if line.strip()]
    values = [_REQUIREMENT_BULLET_RE.sub("", line.strip())
              for line in (requirement.text.splitlines() if requirement else []) if line.strip()]
    values = [value for value in values if not _DELETED_RE.match(value)]

    if law_match := _LAW_RE.match(lines[0]):
        if _DELETED_RE.match(law_match.group(2)):
            skipped.append(AnnexSkippedRow(item_label=law_match.group(1), reason=law_match.group(2)))
            return None
        law, lines = lines[0], lines[1:]
        if not lines:
            if values:
                items.append(_item([], law_match.group(1), law_match.group(2), values, law))
            return law
    text = " ".join(lines)
    sub = _SUB_RE.match(text)
    label, rest = sub.groups() if sub else (None, text)
    if _DELETED_RE.match(rest):
        skipped.append(AnnexSkippedRow(item_label=label, reason=rest))
        return law
    items.append(_item([law] if law else [], label, rest, values, text))
    return law


def _item(path: list[str], label: str | None, text: str, values: list[str], source_text: str) -> AnnexItem:
    name, conditions, exclusions, inclusions = split_qualifier(text)
    category_path, category_phrases = [], ([], [], [])
    if path:
        category_name, *category_phrases = split_qualifier(path[0])
        category_path = [category_name]
    attributes = [AnnexAttribute(name=REQUIREMENT_ATTRIBUTE, values=values)] if values else []
    return AnnexItem(
        category_path=category_path,
        item_label=label,
        item_name=name,
        conditions=[*category_phrases[0], *conditions],
        exclusions=[*category_phrases[1], *exclusions],
        inclusions=[*category_phrases[2], *inclusions],
        attributes=attributes,
        source_text=source_text,
    )
