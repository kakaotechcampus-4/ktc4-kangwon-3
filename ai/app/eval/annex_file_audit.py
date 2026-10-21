"""별표 규칙 파서 결과를 원본 파일과 거꾸로 대조하는 점검. 순수 함수만 둠.

원문 대조(annex_check)는 "출력이 원문에 있는지"만 봄. 여기서는 반대 방향을 봄.
    - 빠진 줄: 원본 칸·문단의 줄이 출력 어디에도 없음
    - 빠진 번호 줄: 원본 칸 머리 번호(①, 1), 가., (가) …)가 번호와 함께 출력에 없음
    - 안 붙은 비고: 품목 묶음의 비고·단서 칸 문구가 묶음 안 어떤 행에 없음
일부러 옮기지 않는 줄(머리글, 제목, "o 대표적인 품목은 다음과 같다." 등)은 뺌.
"""

import re

from ..schemas.annex import AnnexParseOutput
from ..utils.annex_check import normalize
from ..utils.annex_file import Block, Cell, Table
from ..utils.annex_file.text import classify_phrases

_HEADER_WORDS = {"분류", "품목", "세부품목", "대분류", "중분류", "소분류", "대상법령및물품의범위", "구비요건", "비고", "신설"}
_AMENDMENT_RE = re.compile(r"\(\s*신\s*설\s*\)")
# 일부러 옮기지 않는 줄: 별표 머리, 관련 조문 제목, 구획 제목, 대표 품목 머리, 삭제된 문단 번호
_SKIP_LINE_RE = re.compile(r"^(■|[\[【]별표)|관련\)\s*$|^[가-힣]\.\s*(대상법령 및 물품의 범위와 구비요건|물품별 수[출입]요건)$"
                           r"|^o\s*대표적인\s*품목은\s*다음과\s*같다\.?$|^\S+\s*<\s*삭\s*제\s*>$")
_BULLET_RE = re.compile(r"^\s*(o\s*\(정의\)|o|-|ㅇ|※|:)\s*")
_LABEL_RE = re.compile(r"^\s*([①-⑳➀-➉]|\(\d+\)|\([가-힣]\)|\d+\)(?!\s*~)|[가-힣]\)|[가-힣]\.(?!\d)|\d+\.(?!\d))\s*(\S.*)$")
_NOTE_RE = re.compile(r"^\s*(※\s*)?비\s*고")
_BRACKETS = str.maketrans("", "", "()[]（）")
# 나열 조각 최소 길이. 조각이 모두 짧으면("(전화, 데이터, PBX …)") 짧은 조각까지 봄
_MIN_PIECE = 4


def _plain(text: str) -> str:
    return normalize(text).translate(_BRACKETS)


def _output_text(output: AnnexParseOutput) -> str:
    parts = [output.scheme, *output.notes]
    for row in output.skipped:
        parts += [*row.category_path, (row.item_label or "") + row.reason]
    for item in output.items:
        parts += [*item.category_path, (item.item_label or "") + item.item_name, item.source_text,
                  *item.conditions, *item.exclusions, *item.inclusions]
        for attribute in item.attributes:
            parts += [attribute.name, *attribute.values]
    return "\n".join(_plain(part) for part in parts)


def _tables(blocks: list[Block]) -> list[Table]:
    found: list[Table] = []

    def walk(items) -> None:
        for block in items:
            if isinstance(block, Table):
                found.append(block)
                for cell in block.cells:
                    walk(cell.tables)

    walk(blocks)
    return found


def _lines(blocks: list[Block]) -> list[tuple[str, str]]:
    """(위치, 줄) 목록. 위치는 "문단" 또는 "표N 칸행,열"."""
    lines = [("문단", block) for block in blocks if isinstance(block, str)]
    for index, table in enumerate(_tables(blocks)):
        for cell in table.cells:
            lines += [(f"표{index} 칸{cell.row},{cell.col}", line) for line in cell.text.splitlines()]
    return lines


def uncovered_lines(blocks: list[Block], output: AnnexParseOutput) -> list[str]:
    """원본 줄 중 출력 어디에도 없는 줄. 쉼표·괄호로 나뉜 나열은 조각마다 찾음.

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과).
        output: 파싱 결과.

    Returns:
        list[str]: "위치: 줄" 목록.
    """
    hay = _output_text(output)
    missing: list[str] = []
    for where, line in _lines(blocks):
        stripped = _AMENDMENT_RE.sub("", line).strip()
        key = _plain(_BULLET_RE.sub("", stripped)).removesuffix(":")
        if len(key) < 2 or key in hay or key in _HEADER_WORDS or set(key) <= set("○-") or _SKIP_LINE_RE.search(stripped):
            continue
        body = re.sub(r"^\s*(비\s*고\s*[:)]\s*)+", "", _BULLET_RE.sub("", stripped))
        body = _LABEL_RE.sub(r"\2", body)
        pieces = [_plain(piece).removesuffix("등") for piece in re.split(r"[,:/]|[.。]\s|\(|\)", body)]
        pieces = [piece for piece in pieces if len(piece) >= _MIN_PIECE] or [piece for piece in pieces if len(piece) >= 2]
        if pieces and all(piece in hay for piece in pieces):
            continue
        missing.append(f"{where}: {stripped[:80]}")
    return missing


def missing_label_lines(blocks: list[Block], output: AnnexParseOutput) -> list[str]:
    """번호로 시작하는 원본 칸 줄 중, 번호와 그 뒤 글자가 함께 출력에 없는 줄. 비고 칸 안 번호는 뺌.

    Args:
        blocks: 별표 원본 파일의 문단·표.
        output: 파싱 결과.

    Returns:
        list[str]: "위치: 줄" 목록.
    """
    hay = _output_text(output).replace("\n", "")
    missing: list[str] = []
    for index, table in enumerate(_tables(blocks)):
        header_end = max((cell.row + cell.row_span for cell in table.cells if cell.row == 0), default=0)
        for cell in table.cells:
            if cell.row < header_end or _NOTE_RE.match(cell.text):
                continue
            for line in cell.text.splitlines():
                match = _LABEL_RE.match(line)
                if not match:
                    continue
                body = _plain(match.group(2))[:8]
                # 번호 뒤 두 글자로 확인 (분류 이름 뒤 괄호 문구는 한정 문구로 떨어져 나감).
                # 번호를 떼어 뺀 행 사유·문구로 옮긴 조항("4) 다음의 어느 …")은 본문만 확인
                if len(body) >= 2 and _plain(match.group(1)) + body[:2] not in hay and body not in hay:
                    missing.append(f"표{index} 칸{cell.row},{cell.col}: {line.strip()[:80]}")
    return missing


def _locate(tables: list[Table], output: AnnexParseOutput) -> list[tuple[int, Cell, int]]:
    """품목 행마다 (표 번호, 원본 칸, 행 번호). source_text가 든 칸 중 분류가 같은 줄에 있는 칸을 고름."""
    found: list[tuple[int, Cell, int]] = []
    for position, item in enumerate(output.items):
        source = normalize(item.source_text)
        last = normalize(item.category_path[-1])[:6] if item.category_path else None
        fallback = None
        for index, table in enumerate(tables):
            grid = table.grid()
            for cell in table.cells:
                if not source or source not in normalize(cell.text):
                    continue
                fallback = fallback or (index, cell, position)
                if last is None or any(other is not None and other.col < cell.col and normalize(other.text).startswith(last)
                                       for other in grid[cell.row]):
                    found.append((index, cell, position))
                    break
            else:
                continue
            break
        else:
            if fallback:
                found.append(fallback)
    return found


def unattached_notes(blocks: list[Block], output: AnnexParseOutput) -> list[str]:
    """묶음 비고·단서 칸의 첫 문구가 그 묶음(왼쪽 병합 칸의 행 범위) 안 품목 행에 붙지 않은 경우.

    비고 칸("비고: …")과, ○ 없이 오른쪽 끝까지 이어진 제외·포함·한정 조항 칸을 봄.

    Args:
        blocks: 별표 원본 파일의 문단·표.
        output: 파싱 결과.

    Returns:
        list[str]: "위치 '문구' → 품목" 목록.
    """
    tables = _tables(blocks)
    located = _locate(tables, output)
    missing: list[str] = []
    for index, table in enumerate(tables):
        grid = table.grid()
        header_end = max((cell.row + cell.row_span for cell in table.cells if cell.row == 0), default=0)
        for cell in table.cells:
            text = cell.text.strip()
            if cell.row < header_end or cell.col == 0 or not text:
                continue
            marked = any(other is not None and other.text.strip() == "○" for other in grid[cell.row])
            clause = (cell.col_span > 1 and not marked and cell.col + cell.col_span == table.col_count
                      and re.search(r"제외|포함|한정|한함", text) is not None)
            if not (_NOTE_RE.match(text) or clause):
                continue
            left = grid[cell.row][cell.col - 1]
            if left is None:
                continue
            head = re.sub(r"^\s*(※\s*)?비\s*고\s*[:)]?\s*", "", text.splitlines()[0])
            head = _LABEL_RE.sub(r"\2", _BULLET_RE.sub("", head))
            phrases = [phrase for group in classify_phrases(head) for phrase in group]
            if not phrases:
                continue
            rows = range(left.row, left.row + left.row_span)
            for table_index, item_cell, position in located:
                if table_index != index or item_cell.row not in rows or item_cell is cell:
                    continue
                item = output.items[position]
                attached = "".join(_plain(phrase) for phrase in (*item.conditions, *item.exclusions, *item.inclusions))
                lost = next((phrase for phrase in phrases if _plain(phrase)[:25] not in attached), None)
                if lost is not None:
                    missing.append(f"표{index} 칸{cell.row},{cell.col} '{lost[:30]}' → "
                                   f"{item.item_label or ''} {item.item_name[:30]}".strip())
    return missing


def audit_annex(blocks: list[Block], output: AnnexParseOutput) -> dict[str, list[str]]:
    """세 점검을 한 번에 돌린다.

    Returns:
        dict[str, list[str]]: 점검 이름별 걸린 항목. 모두 비면 이상 없음.
    """
    return {
        "빠진 줄": uncovered_lines(blocks, output),
        "빠진 번호 줄": missing_label_lines(blocks, output),
        "안 붙은 비고": unattached_notes(blocks, output),
    }
