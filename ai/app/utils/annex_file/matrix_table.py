"""○ 표시 행렬 표(방송통신기자재 적합성평가 고시 별표 1)를 품목 행으로 푼다. 순수 함수만 둠.

표 모양
    - 머리글 여러 단: 대상기자재(품목 열들) | 적용분야·유형(○ 열들, 위 단이 묶음) | 기기부호 | 기타사항
    - 품목 열: 왼쪽부터 분류 단계, 행의 마지막 칸이 품목. 마지막 칸이 정의·대표 품목 설명이면 바로 왼쪽 칸이 품목
    - "o …" 칸이 자기 ○를 가지면 위 품목 아래 추가 행
    - ○ 열을 가로질러 병합된 칸: 묶음 제외 조항(4) 다음의 어느 하나에 해당하는 기자재는 … 제외한다.)
    - 표 앞 "1. 해상업무용 …" 문단: 구간. category_path 첫 단계
"""

import re
from dataclasses import dataclass

from ...schemas.annex import AnnexAttribute, AnnexItem, AnnexParseOutput, AnnexSkippedRow
from .grid import Block, Cell, Table
from .text import (Phrases, classify_phrases, join_lines, note_entries, scheme_from_title, split_examples,
                   split_listed, split_qualifier)

MARK = "○"
DEFINITION_ATTRIBUTE = "정의"
CATEGORY_DEFINITION_ATTRIBUTE = "분류 정의"
EXAMPLE_ATTRIBUTE = "대표 품목"

_LABEL_RE = re.compile(r"^([①-⑳]|\d+\)|[가-힣]\)|[가-힣]\.)\s*(.+)$", re.DOTALL)
_SECTION_RE = re.compile(r"^\d+\.\s*\S")
_ANNEX_HEADING_RE = re.compile(r"^[\[【]별표|^\(.*관련\)$")
_DEFINITION_RE = re.compile(r"^o\s*\(정의\)\s*")
_EXAMPLES_HEAD_RE = re.compile(r"^o\s*대표적인\s*품목")
_BULLET_RE = re.compile(r"^[o\-]\s+")
# "- 저장장치 : 하드디스크드라이브(HDD), …"처럼 소제목별로 묶인 대표 품목
_EXAMPLE_GROUP_RE = re.compile(r"^-\s*([^:,]+?)\s*:\s*(.+)$")
# 분류 설명 중 적용 범위 문구 ("…제품에 한함", "…기자재에 한정", "…모듈도 포함")
_SCOPE_END_RE = re.compile(r"(한정|한함|한한다|제외|포함)(한다|함|하며|된다)?\.?$")
# "※ 4)~11) : 계절가전"처럼 하위 번호 범위에 붙인 꼬리표
_RANGE_TAG_RE = re.compile(r"\d+\)\s*~\s*\d+\)\s*:")
_NOTE_HEAD_RE = re.compile(r"^※?\s*비\s*고\s*[:)]?\s*$")
# "(삭 제)", "<삭제>"
_DELETED_RE = re.compile(r"^[(<\s]*삭\s*제[)>\s]*$")


@dataclass(frozen=True)
class _Columns:
    """머리글에서 읽은 열 역할. 값은 격자 열 번호."""

    items: tuple[int, ...]
    marks: tuple[tuple[int, str, str], ...]
    values: tuple[tuple[int, str], ...]


@dataclass
class _Draft:
    groups: tuple[int, ...]
    item: AnnexItem
    phrases: Phrases


def is_matrix_table(table: Table) -> bool:
    """머리글 아래에 ○만 적힌 열이 있는 표인지."""
    return bool(_read_columns(table).marks)


def parse_matrix_tables(blocks: list[Block]) -> AnnexParseOutput:
    """○ 표시 행렬 표들로 이루어진 별표를 품목 행으로 푼다.

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과).

    Returns:
        AnnexParseOutput: 품목 행(○ 열은 위 단 머리글별 추가 칸), 뺀 행(번호 붙은 제외 조항), 표 전체 비고.

    Raises:
        ValueError: ○ 행렬 표가 없거나 제목 문단이 없는 경우.
    """
    tables = [block for block in blocks if isinstance(block, Table)]
    if not tables or not all(is_matrix_table(table) for table in tables):
        raise ValueError("○ 표시 행렬 표로 이루어진 별표가 아닙니다.")
    leading = [block for block in blocks[:blocks.index(tables[0])] if isinstance(block, str)]
    titles = [text for text in leading if not _ANNEX_HEADING_RE.match(text) and not _SECTION_RE.match(text)]
    if not titles:
        raise ValueError("별표 제목 문단이 없습니다.")

    drafts: list[_Draft] = []
    skipped: list[AnnexSkippedRow] = []
    notes: list[str] = []
    group_phrases: dict[int, Phrases] = {}
    section: str | None = None
    for block in blocks:
        if isinstance(block, str):
            if _SECTION_RE.match(block):
                section = block
            continue
        _parse_table(block, section, drafts, skipped, notes, group_phrases)

    items = [draft.item.model_copy(update=_phrase_fields(draft, group_phrases)) for draft in drafts]
    # 같은 비고가 표마다 되풀이됨 (전자파흡수율 기준 안내 등)
    notes = list(dict.fromkeys(notes))
    return AnnexParseOutput(scheme=scheme_from_title(titles[0]), items=items, skipped=skipped, notes=notes)


def _header_end(table: Table) -> int:
    return max(cell.row + cell.row_span for cell in table.cells if cell.row == 0)


def _compact(text: str) -> str:
    """머리글 글자. 칸 폭 때문에 낱말 중간에서 줄이 나뉘어 줄을 붙여 이음."""
    return "".join(line.strip() for line in text.splitlines())


def _read_columns(table: Table) -> _Columns:
    grid = table.grid()
    header_end = _header_end(table)
    stacks: list[list[str]] = []
    for col in range(table.col_count):
        stack: list[str] = []
        for row in range(header_end):
            cell = grid[row][col]
            if cell is not None and _compact(cell.text) and (not stack or stack[-1] != _compact(cell.text)):
                stack.append(_compact(cell.text))
        stacks.append(stack)
    item_head = stacks[0][0] if stacks and stacks[0] else None
    items = tuple(col for col, stack in enumerate(stacks) if stack and stack[0] == item_head)

    marks: list[tuple[int, str, str]] = []
    values: list[tuple[int, str]] = []
    for col, stack in enumerate(stacks):
        if col in items or not stack:
            continue
        own = [cell for cell in table.cells
               if cell.col == col and cell.col_span == 1 and cell.row >= header_end]
        texts = {cell.text.strip() for cell in own}
        if MARK in texts and texts <= {MARK, ""}:
            marks.append((col, stack[0], _mark_name(stack)))
        else:
            values.append((col, stack[-1]))
    return _Columns(items=items, marks=tuple(marks), values=tuple(values))


def _mark_name(stack: list[str]) -> str:
    """○ 열 이름. 아래 단 이름, 셋째 단이 있으면 괄호로 붙임 (예: "전자파인체보호(전자파흡수율)")."""
    if len(stack) >= 3:
        return f"{stack[1]}({stack[-1]})"
    return stack[-1]


def _parse_table(table: Table, section: str | None, drafts: list[_Draft], skipped: list[AnnexSkippedRow],
                 notes: list[str], group_phrases: dict[int, Phrases]) -> None:
    columns = _read_columns(table)
    grid = table.grid()
    mark_cols = {col for col, _, _ in columns.marks}
    for index in range(_header_end(table), table.row_count):
        row = grid[index]
        item_cells = _distinct(row[col] for col in columns.items)
        if not item_cells:
            continue
        last = item_cells[-1]
        if last.col == 0 and last.col + last.col_span == table.col_count:
            notes.extend(_note_entries(last.text))
            continue
        if any(col in range(last.col, last.col + last.col_span) for col in mark_cols):
            # ○ 열을 가로지르는 칸: 왼쪽 분류 묶음 전체에 걸리는 조항
            if last.row == index:
                clause_path = [*([section] if section else []), *(_category_name(cell.text) for cell in item_cells[:-1])]
                _add_clause(last, item_cells[:-1], clause_path, skipped, notes, group_phrases)
            continue
        attributes = _row_attributes(row, columns)
        path = [section] if section else []
        if _is_description(last.text):
            if len(item_cells) < 2:
                continue
            item_cell, path_cells = item_cells[-2], item_cells[:-2]
            label, name, phrases, own = _parse_item_cell(item_cell.text)
            description, description_phrases = _parse_description(last.text)
            phrases = phrases.merged(description_phrases)
            attributes = [*_merge_attributes([*own, *description]), *attributes]
            source_text = item_cell.text.splitlines()[0].strip()
        elif _BULLET_RE.match(last.text.strip()) and len(item_cells) >= 2:
            # 위 품목 아래 "o …" 추가 행: 위 품목까지 분류 단계
            path_cells = item_cells[:-1]
            label, name = None, join_lines(_BULLET_RE.sub("", last.text.strip(), count=1))
            phrases, source_text = Phrases(), last.text.strip()
        else:
            path_cells = item_cells[:-1]
            label, name, phrases, own = _parse_item_cell(last.text)
            attributes = [*own, *attributes]
            source_text = last.text.splitlines()[0].strip()
        path += [_category_name(cell.text) for cell in path_cells]
        for cell in path_cells:
            definitions, scope = _category_detail(cell.text)
            if definitions:
                attributes.append(AnnexAttribute(name=f"{CATEGORY_DEFINITION_ATTRIBUTE} - {_category_name(cell.text)}",
                                                 values=definitions))
            phrases = phrases.merged(scope)
        if _DELETED_RE.match(name):
            skipped.append(AnnexSkippedRow(category_path=path, item_label=label, reason=name))
            continue
        item = AnnexItem(category_path=path, item_label=label, item_name=name, conditions=[], exclusions=[],
                         inclusions=[], attributes=attributes, source_text=source_text)
        # 묶음 조항은 분류 칸뿐 아니라 품목 칸 자신 아래에도 옴 (8) 전열기구류 아래 "o 다음에 해당하는 …제외한다.")
        drafts.append(_Draft(groups=tuple(id(cell) for cell in item_cells), item=item, phrases=phrases))


def _distinct(cells) -> list[Cell]:
    result: list[Cell] = []
    for cell in cells:
        if cell is not None and cell.text.strip() and all(cell is not other for other in result):
            result.append(cell)
    return result


def _is_description(text: str) -> bool:
    first = text.strip().splitlines()[0] if text.strip() else ""
    return bool(_DEFINITION_RE.match(first) or _EXAMPLES_HEAD_RE.match(first) or first.startswith("※"))


def _category_name(text: str) -> str:
    """분류 칸 이름. 이름 뒤 ": 설명", "※ …" 줄은 뺌."""
    lines: list[str] = []
    for line in (line.strip() for line in text.splitlines()):
        if line.startswith((":", "※", "o ", "- ")) or _SECTION_RE.match(line) and lines:
            break
        lines.append(line)
    return join_lines("\n".join(lines))


def _category_detail(text: str) -> tuple[list[str], Phrases]:
    """분류 칸 이름 뒤 설명 줄을 (분류 정의, 문구)로 나눈다.

    ": …" 줄은 분류 정의. 다만 적용 범위로 끝나면("…제품에 한함") 문구로 넣음 (대상 판단에 쓰이는 조건이라).
    "※ …" 줄은 문구, 하위 번호 범위 꼬리표("※ 4)~11) : 계절가전")는 분류 정의. 표시 없는 줄은 앞 줄에 이어 붙임.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    start = next((index for index, line in enumerate(lines) if line.startswith((":", "※"))), len(lines))
    entries: list[str] = []
    for line in lines[start:]:
        if line.startswith((":", "※")) or not entries:
            entries.append(line)
        elif _RANGE_TAG_RE.match(line):
            entries.append(f"※ {line}")
        else:
            entries[-1] = f"{entries[-1]} {line}"
    definitions: list[str] = []
    phrases = Phrases()
    for entry in entries:
        body = entry.lstrip(":※ ").strip()
        if entry.startswith(":") and not _SCOPE_END_RE.search(body) or _RANGE_TAG_RE.match(body):
            definitions.append(body)
        else:
            phrases.extend(*classify_phrases(body))
    return definitions, phrases


def _parse_item_cell(text: str) -> tuple[str | None, str, Phrases, list[AnnexAttribute]]:
    """품목 칸을 (번호, 이름, 문구, 설명 칸)으로 나눈다.

    이름 뒤 ": 설명" 줄은 정의 칸, "※" 줄은 문구. 번호 칸 안에 "o (정의) …", "o 대표적인 품목 …"이
    같이 있으면(고시 별표 1 표 11의 ① 컴퓨터 및 컴퓨터 시스템 등) 그 줄부터 설명 칸으로 읽음.
    이름 끝 괄호의 한정·제외·포함 문구와 품목 나열은 떼어 냄.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    start = next((index for index, line in enumerate(lines) if _starts_detail(line)), len(lines))
    definitions: list[str] = []
    phrases = Phrases()
    attributes: list[AnnexAttribute] = []
    for index in range(start, len(lines)):
        line = lines[index]
        if line.startswith(":"):
            definitions.append(line.lstrip(": ").strip())
        elif line.startswith("※"):
            phrases.extend(*classify_phrases(line.lstrip("※ ").strip()))
        elif definitions and not _starts_detail(line):
            definitions[-1] = f"{definitions[-1]} {line}"
        else:
            description, description_phrases = _parse_description("\n".join(lines[index:]))
            attributes += description
            phrases = phrases.merged(description_phrases)
            break
    full = join_lines("\n".join(lines[:start]))
    match = _LABEL_RE.match(full)
    label, name = match.groups() if match else (None, full)
    name, *own = split_qualifier(name)
    name, examples = split_examples(name)
    phrases = Phrases(*own).merged(phrases)
    if definitions:
        attributes.insert(0, AnnexAttribute(name=DEFINITION_ATTRIBUTE, values=definitions))
    return label, name, phrases, _merge_attributes([*attributes, *examples])


def _starts_detail(line: str) -> bool:
    """이름 뒤 설명 줄의 시작인지 (": …", "※ …", "o …", "- …")."""
    return line.startswith((":", "※")) or bool(_DEFINITION_RE.match(line) or _BULLET_RE.match(line))


def _parse_description(text: str) -> tuple[list[AnnexAttribute], Phrases]:
    """정의·대표 품목 설명 칸을 추가 칸과 문구로 나눈다."""
    definitions: list[str] = []
    examples: dict[str, list[str]] = {}
    phrases = Phrases()
    current: list[str] | None = None
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if _DEFINITION_RE.match(line):
            definitions.append(_DEFINITION_RE.sub("", line))
            current = definitions
        elif _EXAMPLES_HEAD_RE.match(line):
            current = None
        elif line.startswith("※") or line.startswith("o "):
            phrases.extend(*classify_phrases(_BULLET_RE.sub("", line.lstrip("※ ").strip())))
            current = None
        elif line.startswith("-") and current is definitions:
            # "o (정의)" 아래 "- …" 줄마다 정의 하나
            definitions.append(_BULLET_RE.sub("", line))
        elif line.startswith("-"):
            group = _EXAMPLE_GROUP_RE.match(line)
            name = f"{EXAMPLE_ATTRIBUTE} - {group.group(1)}" if group else EXAMPLE_ATTRIBUTE
            values = split_listed(group.group(2) if group else line)
            examples.setdefault(name, []).extend(values)
            current = examples[name]
        elif current is definitions:
            definitions[-1] = f"{definitions[-1]} {line}"
        elif current is not None:
            current.extend(split_listed(line))
    definitions = [definition for definition in definitions if definition]
    attributes = [AnnexAttribute(name=DEFINITION_ATTRIBUTE, values=definitions)] if definitions else []
    attributes += [AnnexAttribute(name=name, values=values) for name, values in examples.items() if values]
    return attributes, phrases


def _merge_attributes(attributes: list[AnnexAttribute]) -> list[AnnexAttribute]:
    """이름이 같은 칸(품목 칸 ": 설명"과 설명 칸 "(정의)")을 하나로 합친다."""
    merged: dict[str, list[str]] = {}
    for attribute in attributes:
        merged.setdefault(attribute.name, []).extend(attribute.values)
    return [AnnexAttribute(name=name, values=values) for name, values in merged.items()]


def _row_attributes(row: list[Cell | None], columns: _Columns) -> list[AnnexAttribute]:
    """○ 열은 위 단 머리글별로 ○ 열 이름을 묶고, 값 열(기기부호 등)은 칸 글자를 값으로."""
    groups: dict[str, list[str]] = {}
    for col, group, name in columns.marks:
        cell = row[col]
        if cell is not None and cell.text.strip() == MARK:
            groups.setdefault(group, []).append(name)
    attributes = [AnnexAttribute(name=group, values=names) for group, names in groups.items()]
    for col, name in columns.values:
        cell = row[col]
        if cell is not None and cell.text.strip():
            attributes.append(AnnexAttribute(name=name, values=[join_lines(cell.text)]))
    return attributes


def _add_clause(cell: Cell, left: list[Cell], path: list[str], skipped: list[AnnexSkippedRow], notes: list[str],
                group_phrases: dict[int, Phrases]) -> None:
    """묶음 조항 칸. 번호가 있으면 뺀 행으로 남기고, 조항 문구는 왼쪽 분류 묶음의 문구로 붙임."""
    lines = [line.strip() for line in cell.text.splitlines() if line.strip()]
    match = _LABEL_RE.match(lines[0])
    if match:
        label, lines[0] = match.groups()
        skipped.append(AnnexSkippedRow(category_path=path, item_label=label, reason=lines[0]))
    head = _BULLET_RE.sub("", lines[0]).lstrip("※ ").strip()
    conditions, exclusions, inclusions = classify_phrases(head)
    # 나열 항목은 "o"·"-" 줄마다 하나. 표시 없는 줄("(다만, … 대상임)")은 앞 항목의 단서라 이어 붙임
    listed: list[str] = []
    for line in lines[1:]:
        if _BULLET_RE.match(line) or not listed:
            listed.append(_BULLET_RE.sub("", line))
        else:
            listed[-1] = f"{listed[-1]} {line}"
    # 조항 아래 나열은 조항과 같은 종류 문구
    if exclusions:
        exclusions += listed
    elif inclusions:
        inclusions += listed
    else:
        conditions += listed
    if not left:
        notes.extend([head, *listed])
        return
    group_phrases.setdefault(id(left[-1]), Phrases()).extend(conditions, exclusions, inclusions)


def _note_entries(text: str) -> list[str]:
    lines = text.strip().splitlines()
    if lines and _NOTE_HEAD_RE.match(lines[0].strip()):
        lines = lines[1:]
    return [_BULLET_RE.sub("", entry) for entry in note_entries("\n".join(lines))]


def _phrase_fields(draft: _Draft, group_phrases: dict[int, Phrases]) -> dict[str, list[str]]:
    phrases = draft.phrases.merged(*(group_phrases.get(group) for group in draft.groups))
    return {"conditions": phrases.conditions, "exclusions": phrases.exclusions, "inclusions": phrases.inclusions}
