"""품목이 행마다 놓인 표(시행규칙 대상제품 별표, 어린이제품 적용 안전기준, 전파법 면제대상)를 품목 행으로 푼다.

순수 함수만 둠.

표 모양
    - 전체 폭 칸: 표 제목·구간("1. 안전인증대상전기용품")·비고. 제목·구간 다음 행이 열 이름 행
    - 열 이름: "분류" 열은 분류 단계, "품목" 열(없으면 첫 열)은 품목, 나머지 열은 추가 칸
      (예: 적용 안전기준, 면제 수량, 면제 내용)
    - 품목 칸의 번호 줄(1), 가.) 하나가 행 하나. 번호가 없으면 칸 전체가 행 하나
    - 품목 열의 비고: 같은 분류 칸(병합)의 행들에 붙임. 표 뒤 비고 문단·전체 폭 비고: 표 전체 비고
"""

import re
from dataclasses import dataclass

from ...schemas.annex import AnnexAttribute, AnnexItem, AnnexParseOutput, AnnexSkippedRow
from .grid import Block, Cell, Table
from .text import (Phrases, classify_phrases, find_title, is_deleted, is_no_target, is_note, join_lines,
                   note_entries, scheme_from_title, split_examples, split_qualifier)

_CATEGORY_HEADER = "분류"
_ITEM_HEADER = "품목"
_LABEL_RE = re.compile(r"^(\d+\)|\d+\.|[가-힣]\.)\s*(.+)$")
_DELETED_LABEL_RE = re.compile(r"^(\d+\)|\d+\.|[가-힣]\.?)\s*(<?삭\s*제.*)$")
_SECTION_RE = re.compile(r"^\d+\.\s")
# "자. … 반입하는 기자재. 다만, … 제외한다."처럼 이름 뒤에 붙은 단서 문장
_PROVISO_RE = re.compile(r"\.\s+(?=다만)")


@dataclass(frozen=True)
class _Columns:
    """열 이름 행에서 읽은 열 역할. 값은 격자 열 번호."""

    category: int | None
    item: int
    attributes: tuple[tuple[int, str], ...]


@dataclass
class _Draft:
    """묶음 비고를 붙이기 전 품목 행. 비고는 묶음 아래쪽에 있어 표를 다 읽은 뒤 붙임."""

    group: Cell | None
    item: AnnexItem
    phrases: Phrases


def parse_row_table(blocks: list[Block]) -> AnnexParseOutput:
    """품목이 행마다 놓인 별표 표 하나를 품목 행으로 푼다.

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과). 표가 하나여야 함.

    Returns:
        AnnexParseOutput: 품목 행, 뺀 행(삭제·대상 없음), 표 전체 비고. 구간이 있으면 category_path 첫 단계.

    Raises:
        ValueError: 표가 하나가 아니거나, 제목 또는 열 이름 행을 찾지 못한 경우.
    """
    tables = [block for block in blocks if isinstance(block, Table)]
    if len(tables) != 1:
        raise ValueError(f"표가 하나인 별표가 아닙니다 (표 {len(tables)}개).")
    table = tables[0]
    position = blocks.index(table)
    title = find_title([block for block in blocks[:position] if isinstance(block, str)])
    after = [block for block in blocks[position + 1:] if isinstance(block, str)]
    notes = note_entries("\n".join(after)) if after else []

    grid = table.grid()
    last_row = max((index for index, row in enumerate(grid) if _filled(row)), default=-1)
    drafts: list[_Draft] = []
    skipped: list[AnnexSkippedRow] = []
    group_phrases: dict[int, Phrases] = {}
    section: str | None = None
    columns: _Columns | None = None
    seen: set[int] = set()

    for index, row in enumerate(grid):
        cells = _filled(row)
        if not cells:
            continue
        if len(cells) == 1 and _is_full_width(cells[0], table.col_count):
            text = cells[0].text
            if is_note(text) or index == last_row:
                notes.extend(note_entries(text))
                continue
            for line in (line.strip() for line in text.splitlines()):
                if _SECTION_RE.match(line):
                    section = line
                elif line and title is None:
                    title = line
            columns = None
            continue
        if columns is None:
            columns = _read_columns(cells)
            continue

        item_cell = row[columns.item]
        if item_cell is None or not item_cell.text.strip() or id(item_cell) in seen:
            continue
        category_cell = row[columns.category] if columns.category is not None else None
        if is_note(item_cell.text):
            if category_cell is not None and category_cell.row_span > 1:
                group_phrases.setdefault(id(category_cell), Phrases()).extend(*classify_phrases(item_cell.text))
            else:
                notes.extend(note_entries(item_cell.text))
            continue
        seen.add(id(item_cell))

        path = [section] if section else []
        category_phrases = Phrases()
        if category_cell is not None and category_cell is not item_cell:
            category_name, *phrases = split_qualifier(join_lines(category_cell.text))
            path.append(category_name)
            category_phrases.extend(*phrases)
        attributes = _attributes(row, columns, item_cell, category_cell)
        for line in _item_lines(item_cell.text):
            _add_line(drafts, skipped, line, path, category_phrases, attributes, category_cell)

    if title is None:
        raise ValueError("별표 제목을 찾지 못했습니다.")
    items = [_finish(draft, group_phrases) for draft in drafts]
    return AnnexParseOutput(scheme=scheme_from_title(title), items=items, skipped=skipped, notes=notes)


def _filled(row: list[Cell | None]) -> list[Cell]:
    """행의 글자 있는 칸. 병합으로 되풀이된 칸은 한 번만."""
    cells: list[Cell] = []
    for cell in row:
        if cell is not None and cell.text.strip() and all(cell is not other for other in cells):
            cells.append(cell)
    return cells


def _is_full_width(cell: Cell, col_count: int) -> bool:
    # 앞 열이 비어 있는 표(전파법 시행령 별표 6의2)는 둘째 열부터 끝까지 이어진 칸
    return cell.col_span >= 2 and cell.col + cell.col_span == col_count


def _read_columns(cells: list[Cell]) -> _Columns:
    names = [(cell.col, join_lines(cell.text)) for cell in cells]
    compact = {col: "".join(name.split()) for col, name in names}
    category = next((col for col, name in compact.items() if name == _CATEGORY_HEADER), None)
    item = next((col for col, name in compact.items() if name == _ITEM_HEADER),
                next(col for col, _ in names if col != category))
    attributes = tuple((col, name) for col, name in names if col not in (category, item))
    return _Columns(category=category, item=item, attributes=attributes)


def _attributes(row: list[Cell | None], columns: _Columns, item_cell: Cell,
                category_cell: Cell | None) -> list[AnnexAttribute]:
    """추가 칸 값. 칸 안 줄마다 값 하나 (번호는 원문대로 둠)."""
    attributes: list[AnnexAttribute] = []
    for col, name in columns.attributes:
        cell = row[col]
        if cell is None or cell is item_cell or cell is category_cell:
            continue
        values = [line.strip() for line in cell.text.splitlines() if line.strip()]
        if values:
            attributes.append(AnnexAttribute(name=name, values=values))
    return attributes


def _item_lines(text: str) -> list[str]:
    """품목 칸을 번호 줄마다 나눈다. 번호 없는 줄은 앞 줄에 이어 붙임."""
    lines: list[str] = []
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if lines and not _LABEL_RE.match(line):
            lines[-1] = f"{lines[-1]} {line}"
        else:
            lines.append(line)
    return lines


def _add_line(drafts: list[_Draft], skipped: list[AnnexSkippedRow], line: str, path: list[str],
              category_phrases: Phrases, attributes: list[AnnexAttribute], group: Cell | None) -> None:
    if is_no_target(line):
        skipped.append(AnnexSkippedRow(item_label=None, reason=line))
        return
    if deleted := _DELETED_LABEL_RE.match(line):
        skipped.append(AnnexSkippedRow(item_label=deleted.group(1), reason=deleted.group(2)))
        return
    if is_deleted(line):
        skipped.append(AnnexSkippedRow(item_label=None, reason=line))
        return
    label_match = _LABEL_RE.match(line)
    label, rest = label_match.groups() if label_match else (None, line)
    name_part, *proviso = _PROVISO_RE.split(rest, maxsplit=1)
    name, *own = split_qualifier(name_part)
    name, examples = split_examples(name)
    phrases = category_phrases.merged(Phrases(*own))
    for sentence in proviso:
        phrases.extend(*classify_phrases(sentence))
    item = AnnexItem(category_path=list(path), item_label=label, item_name=name, conditions=[], exclusions=[],
                     inclusions=[], attributes=[*attributes, *examples], source_text=line)
    drafts.append(_Draft(group=group, item=item, phrases=phrases))


def _finish(draft: _Draft, group_phrases: dict[int, Phrases]) -> AnnexItem:
    """묶음 비고(분류 칸 단위)를 붙여 품목 행을 만든다."""
    phrases = draft.phrases.merged(group_phrases.get(id(draft.group)) if draft.group is not None else None)
    return draft.item.model_copy(update={
        "conditions": phrases.conditions,
        "exclusions": phrases.exclusions,
        "inclusions": phrases.inclusions,
    })
