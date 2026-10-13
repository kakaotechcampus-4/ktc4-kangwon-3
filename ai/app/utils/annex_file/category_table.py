"""분류·품목·세부품목 3칸 표(운용요령 별표 1~7)를 품목 행으로 푼다. 순수 함수만 둠.

표 모양
    - 분류 칸(1열)은 아래 품목 행들과 병합됨. 품목 칸(2열)은 묶음 비고 행과 병합되기도 함
    - 세부품목 칸(3열)의 번호(①) 줄 하나가 행 하나. 세부품목이 없으면 품목이 행 하나
    - 비고 위치로 적용 범위가 갈림: 3열 비고 → 같은 품목 칸, 2~3열 병합 비고 → 같은 분류 칸, 전체 병합 비고 → 표 전체
"""

import re
from dataclasses import dataclass

from ...schemas.annex import AnnexAttribute, AnnexItem, AnnexParseOutput, AnnexSkippedRow
from .grid import Block, Cell, Table
from .text import (Phrases, classify_phrases, find_title, is_deleted, is_no_target, is_note, join_lines, note_entries,
                   scheme_from_title, split_examples, split_qualifier)

HEADER = ("분류", "품목", "세부품목")

# ➀~➉: 운용요령 별표 5에 ⑤ 대신 섞여 쓰임
_CIRCLED_RE = re.compile(r"^([①-⑳➀-➉])\s*(.*)$")
_ITEM_LABEL_RE = re.compile(r"^([가-힣]\.)\s*(.+)$")
# "바 삭제<2018.12.31>"처럼 점이 빠진 번호도 있음
_DELETED_LABEL_RE = re.compile(r"^([가-힣]\.?)\s*(<?삭\s*제.*)$")


@dataclass
class _Draft:
    """비고를 붙이기 전 품목 행. 비고는 표 아래쪽에 있어 표를 다 읽은 뒤 붙임."""

    groups: tuple[Cell, ...]
    category_path: list[str]
    item_label: str | None
    item_name: str
    phrases: Phrases
    attributes: list[AnnexAttribute]
    source_text: str


def is_category_table(table: Table) -> bool:
    """머리 행이 분류·품목·세부품목인 3칸 표인지."""
    if table.col_count != len(HEADER) or table.row_count < 2:
        return False
    return tuple("".join(cell.text.split()) if cell else "" for cell in table.grid()[0]) == HEADER


def parse_category_table(blocks: list[Block]) -> AnnexParseOutput:
    """분류·품목·세부품목 표 별표를 품목 행으로 푼다.

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과). 첫 표가 분류·품목·세부품목 표여야 함.

    Returns:
        AnnexParseOutput: 품목 행, 뺀 행(삭제·대상 없음), 표 전체 비고.

    Raises:
        ValueError: 분류·품목·세부품목 표가 없거나 제목 문단이 없는 경우.
    """
    tables = [block for block in blocks if isinstance(block, Table)]
    if not tables or not is_category_table(tables[0]):
        raise ValueError("분류·품목·세부품목 표가 아닙니다.")
    title = find_title([block for block in blocks[:blocks.index(tables[0])] if isinstance(block, str)])
    if title is None:
        raise ValueError("별표 제목 문단이 없습니다.")

    drafts: list[_Draft] = []
    skipped: list[AnnexSkippedRow] = []
    notes: list[str] = []
    group_phrases: dict[int, Phrases] = {}
    seen: set[int] = set()

    for category, product, detail in tables[0].grid()[1:]:
        if category is product is detail:
            notes.extend(note_entries(category.text))
            continue
        if product is detail:
            if is_note(product.text):
                group_phrases.setdefault(id(category), Phrases()).extend(*classify_phrases(product.text))
            elif id(product) not in seen:
                _add_product(drafts, skipped, category, product)
            seen.add(id(product))
            continue
        if detail is not None and is_note(detail.text):
            group_phrases.setdefault(id(product), Phrases()).extend(*classify_phrases(detail.text))
            continue
        detail_text = detail.text.strip() if detail else ""
        if id(product) in seen:
            continue
        if not detail_text or detail_text == "-" or is_deleted(detail_text):
            # 세부품목이 없거나, 품목이 삭제돼 세부품목 칸에도 삭제 표시만 있는 행
            _add_product(drafts, skipped, category, product)
            seen.add(id(product))
            continue
        _add_details(drafts, skipped, category, product, detail)

    items = [_finish(draft, group_phrases) for draft in drafts]
    return AnnexParseOutput(scheme=scheme_from_title(title), items=items, skipped=skipped, notes=notes)


def _category_step(cell: Cell) -> tuple[str, Phrases]:
    name, *phrases = split_qualifier(join_lines(cell.text))
    step = Phrases()
    step.extend(*phrases)
    return name, step


def _add_product(drafts: list[_Draft], skipped: list[AnnexSkippedRow], category: Cell, product: Cell) -> None:
    """세부품목 없이 품목 칸이 행 하나인 경우. 삭제·대상 없음은 뺀 행으로."""
    text = join_lines(product.text)
    if is_no_target(text):
        skipped.append(AnnexSkippedRow(item_label=None, reason=text))
        return
    if deleted := _DELETED_LABEL_RE.match(text):
        skipped.append(AnnexSkippedRow(item_label=deleted.group(1), reason=deleted.group(2)))
        return
    category_name, phrases = _category_step(category)
    label_match = _ITEM_LABEL_RE.match(text)
    label, rest = label_match.groups() if label_match else (None, text)
    name, *own = split_qualifier(rest)
    phrases.extend(*own)
    name, attributes = split_examples(name)
    drafts.append(_Draft(groups=(category, product), category_path=[category_name], item_label=label,
                         item_name=name, phrases=phrases, attributes=attributes, source_text=text))


def _add_details(drafts: list[_Draft], skipped: list[AnnexSkippedRow], category: Cell, product: Cell,
                 detail: Cell) -> None:
    """세부품목 칸의 번호 줄마다 행 하나. 번호 없는 줄은 대부분 앞 품목이 다음 문단으로 넘어간 것이라 이어 붙임.

    앞 줄이 괄호로 닫혀 끝나고 이 줄이 괄호로 시작하지 않을 때만 번호 없는 행으로 봄
    (운용요령 별표 1 "투광조명기구"는 원문에 ⑦이 빠져 있음).
    """
    category_name, category_phrases = _category_step(category)
    product_name, product_phrases = _category_step(product)
    path = [category_name]
    # 품목 칸과 세부품목 칸에 같은 글자가 나란히 있으면(운용요령 별표 3의2) 품목은 분류 단계가 아님
    if "".join(product.text.split()) != "".join(detail.text.split()):
        path.append(product_name)
    else:
        product_phrases = Phrases()

    lines: list[str] = []
    for line in (line.strip() for line in detail.text.splitlines()):
        if not line:
            continue
        if lines and not _CIRCLED_RE.match(line) and _continues(lines[-1], line):
            lines[-1] = f"{lines[-1]} {line}"
        else:
            lines.append(line)

    for line in lines:
        label_match = _CIRCLED_RE.match(line)
        label, rest = label_match.groups() if label_match else (None, line)
        if is_deleted(rest):
            skipped.append(AnnexSkippedRow(item_label=label, reason=rest))
            continue
        name, *own = split_qualifier(rest)
        name, attributes = split_examples(name)
        phrases = Phrases()
        for step in (category_phrases, product_phrases):
            phrases.extend(step.conditions, step.exclusions, step.inclusions)
        phrases.extend(*own)
        drafts.append(_Draft(groups=(category, product), category_path=list(path), item_label=label,
                             item_name=name, phrases=phrases, attributes=attributes, source_text=line))


def _continues(previous: str, line: str) -> bool:
    return not previous.endswith((")", "]")) or line.startswith(("(", "["))


def _finish(draft: _Draft, group_phrases: dict[int, Phrases]) -> AnnexItem:
    """묶음 비고(분류·품목 칸 단위)를 붙여 품목 행을 만든다."""
    phrases = Phrases()
    phrases.extend(draft.phrases.conditions, draft.phrases.exclusions, draft.phrases.inclusions)
    for group in draft.groups:
        if group_note := group_phrases.get(id(group)):
            phrases.extend(group_note.conditions, group_note.exclusions, group_note.inclusions)
    return AnnexItem(
        category_path=draft.category_path,
        item_label=draft.item_label,
        item_name=draft.item_name,
        conditions=phrases.conditions,
        exclusions=phrases.exclusions,
        inclusions=phrases.inclusions,
        attributes=draft.attributes,
        source_text=draft.source_text,
    )
