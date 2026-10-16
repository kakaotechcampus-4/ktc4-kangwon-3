"""별표 원본 파일(HWP·HWPX)을 본문 순서의 문단·표 목록으로 읽는다.

- HWP(5.0): hwp-hwpx-parser의 구역 압축 해제·레코드 나누기 함수로 레코드를 꺼냄. 비공개 함수에 기대므로
  이 모듈에만 두고 라이브러리 버전 고정. 칸 주소·병합(라이브러리 표 추출은 버림)과 문단 글자
  (라이브러리 해석은 닫는 조판 부호를 여는 부호로 읽어 뒤 글자를 건너뜀)는 규격대로 직접 읽음
- HWPX: zip 안 Contents/section*.xml의 표(tbl)·칸(tc)을 그대로 읽음

레코드 단계 (HWP)
    본문 문단 글자: 1단계 / 표(TABLE)·칸(LIST_HEADER): 표 단계 / 칸 안 문단 글자: 표 단계 + 1

칸 안 표는 칸 하나짜리(상자)면 글자로 풀고, 칸이 여럿이면 표로 둠. 칸 안에 표를 둔 틀 표는 벗김.
"""

import io
import re
import struct
import tempfile
import zipfile
from collections.abc import Iterator
from xml.etree import ElementTree

from hwp_hwpx_parser.hwp5 import HWP5Reader

from .grid import Block, Cell, Table, unwrap_frames

# HWP 레코드 태그 (HWPTAG_BEGIN 0x10 기준)
_PARA_TEXT = 0x10 + 51
_LIST_HEADER = 0x10 + 56
_TABLE = 0x10 + 61
_BODY_PARA_LEVEL = 1
# LIST_HEADER 안 칸 속성 위치: 열·행 주소, 열·행 병합 수 (각 UINT16)
_CELL_ADDR_OFFSET = 8
# 문단 글자 안 조판 부호: 8글자(16바이트) 차지하는 부호, 1글자 부호 중 글자로 바꿀 것
_WIDE_CONTROLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
_WIDE_CONTROL_UNITS = 8
_CHAR_CONTROLS = {9: " ", 10: "\n", 24: "-", 30: " ", 31: " "}

_HWPX_NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}
_HWPX_SECTION_RE = re.compile(r"Contents/section(\d+)\.xml")
# 기호 글꼴 사적 영역 가운뎃점 → 보통 가운뎃점 ("전기\uf09e전동" → "전기·전동", API 별표내용에서는 ?로 깨짐)
_PRIVATE_CHARS = str.maketrans({"\uf09e": "·", "\uf0a0": "·"})


def read_annex_file(content: bytes, file_type: str) -> list[Block]:
    """별표 원본 파일을 본문 순서의 문단 글자와 표로 읽는다.

    Args:
        content: 파일 바이트.
        file_type: 파일 형식 ("hwp" 또는 "hwpx").

    Returns:
        list[Block]: 본문 순서의 문단 글자(str)와 표(Table). 빈 문단은 뺌.

    Raises:
        ValueError: 지원하지 않는 형식이거나, 파일이 깨졌거나 암호가 걸린 경우.
    """
    if file_type == "hwp":
        return unwrap_frames(_read_hwp(content))
    if file_type == "hwpx":
        return unwrap_frames(_read_hwpx(content))
    raise ValueError(f"지원하지 않는 별표 파일 형식: {file_type}")


def _read_hwp(content: bytes) -> list[Block]:
    # 라이브러리가 파일 경로만 받아 임시 파일로 넘김. Windows는 연 채로 다시 열 수 없어 임시 폴더에 쓰고 닫은 뒤 읽음
    with tempfile.TemporaryDirectory() as folder:
        path = f"{folder}/annex.hwp"
        with open(path, "wb") as file:
            file.write(content)
        with HWP5Reader(path) as reader:
            if not reader.is_valid():
                raise ValueError("HWP 파일이 아니거나 깨졌습니다.")
            if reader.is_encrypted():
                raise ValueError("암호가 걸린 HWP 파일입니다.")
            blocks: list[Block] = []
            for section in reader._iter_sections():
                records = list(reader._parse_records(reader._read_section(section)))
                blocks.extend(_hwp_blocks(records))
            return blocks


def _hwp_blocks(records: list[tuple[int, int, bytes]]) -> Iterator[Block]:
    index = 0
    while index < len(records):
        tag, level, data = records[index]
        if tag == _TABLE:
            table, index = _hwp_table(records, index)
            yield table
            continue
        if tag == _PARA_TEXT and level == _BODY_PARA_LEVEL:
            text = _decode_hwp_paragraph(data).strip()
            if text:
                yield text
        index += 1


def _decode_hwp_paragraph(data: bytes) -> str:
    """PARA_TEXT 레코드(UTF-16LE)를 글자로 바꾼다. 조판 부호는 빼고 탭·줄바꿈·하이픈·공백만 글자로 남김."""
    codes = struct.unpack_from(f"<{len(data) // 2}H", data)
    units: list[int] = []
    index = 0
    while index < len(codes):
        code = codes[index]
        if code < 32:
            if code in _CHAR_CONTROLS:
                units.append(ord(_CHAR_CONTROLS[code]))
            index += _WIDE_CONTROL_UNITS if code in _WIDE_CONTROLS else 1
            continue
        units.append(code)
        index += 1
    return struct.pack(f"<{len(units)}H", *units).decode("utf-16-le", errors="replace").translate(_PRIVATE_CHARS)


def _hwp_table(records: list[tuple[int, int, bytes]], start: int) -> tuple[Table, int]:
    """TABLE 레코드부터 표 하나를 읽고, 표 다음 레코드 위치를 함께 돌려준다."""
    table_level = records[start][1]
    cells: list[Cell] = []
    index = start + 1
    while index < len(records) and records[index][1] >= table_level:
        tag, level, data = records[index]
        if tag == _LIST_HEADER and level == table_level:
            cell, index = _hwp_cell(records, index, table_level)
            cells.append(cell)
            continue
        index += 1
    return Table(tuple(cells)), index


def _hwp_cell(records: list[tuple[int, int, bytes]], start: int, table_level: int) -> tuple[Cell, int]:
    col, row, col_span, row_span = struct.unpack_from("<HHHH", records[start][2], _CELL_ADDR_OFFSET)
    content: list[Block] = []
    index = start + 1
    while index < len(records):
        tag, level, data = records[index]
        if level < table_level or (tag == _LIST_HEADER and level == table_level):
            break
        if tag == _TABLE:
            nested, index = _hwp_table(records, index)
            content.extend(_nested_content(nested))
            continue
        if tag == _PARA_TEXT and level == table_level + 1:
            text = _decode_hwp_paragraph(data).strip()
            if text:
                content.append(text)
        index += 1
    cell = Cell(row=row, col=col, row_span=max(row_span, 1), col_span=max(col_span, 1), content=tuple(content))
    return cell, index


def _nested_content(table: Table) -> list[Block]:
    """칸 안 표를 칸 내용으로 바꾼다. 칸 하나짜리(상자)는 글자로 풂."""
    if len(table.cells) == 1:
        return list(table.cells[0].content)
    return [table]


def _read_hwpx(content: bytes) -> list[Block]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            sections = sorted(
                (match for name in archive.namelist() if (match := _HWPX_SECTION_RE.fullmatch(name))),
                key=lambda match: int(match.group(1)),
            )
            roots = [ElementTree.fromstring(archive.read(match.group(0))) for match in sections]
    except (zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ValueError("HWPX 파일이 아니거나 깨졌습니다.") from error
    if not roots:
        raise ValueError("HWPX 파일에 본문 구역이 없습니다.")
    blocks: list[Block] = []
    for root in roots:
        for paragraph in root.iterfind("hp:p", _HWPX_NS):
            text = _hwpx_text(paragraph)
            if text:
                blocks.append(text)
            blocks.extend(_hwpx_table(table) for table in paragraph.iterfind("hp:run/hp:tbl", _HWPX_NS))
    return blocks


def _hwpx_table(table: ElementTree.Element) -> Table:
    cells: list[Cell] = []
    for cell in table.iterfind("hp:tr/hp:tc", _HWPX_NS):
        address = cell.find("hp:cellAddr", _HWPX_NS)
        span = cell.find("hp:cellSpan", _HWPX_NS)
        content: list[Block] = []
        for paragraph in cell.iterfind("hp:subList/hp:p", _HWPX_NS):
            text = _hwpx_text(paragraph)
            if text:
                content.append(text)
            for nested in paragraph.iterfind("hp:run/hp:tbl", _HWPX_NS):
                content.extend(_nested_content(_hwpx_table(nested)))
        cells.append(Cell(
            row=int(address.get("rowAddr")),
            col=int(address.get("colAddr")),
            row_span=max(int(span.get("rowSpan")), 1) if span is not None else 1,
            col_span=max(int(span.get("colSpan")), 1) if span is not None else 1,
            content=tuple(content),
        ))
    return Table(tuple(cells))


def _hwpx_text(paragraph: ElementTree.Element) -> str:
    """문단 글자를 잇는다. 칸 안 표(tbl) 글자는 넣지 않음. 탭은 공백, 줄바꿈은 줄바꿈으로."""
    parts: list[str] = []
    for text in paragraph.iterfind("hp:run/hp:t", _HWPX_NS):
        parts.append(text.text or "")
        for child in text:
            name = child.tag.rsplit("}", 1)[-1]
            parts.append({"tab": " ", "lineBreak": "\n"}.get(name, ""))
            parts.append(child.tail or "")
    return "".join(parts).translate(_PRIVATE_CHARS).strip()
