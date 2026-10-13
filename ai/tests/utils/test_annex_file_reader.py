"""별표 원본 파일 리더가 HWP 레코드·HWPX XML을 문단과 병합 칸이 있는 표로 읽는지 확인한다.

파일 없이 테스트 안에서 레코드·XML을 만듦. 실제 파일은 tests/integration/test_law_api.py에서 받아 읽음.
"""

import io
import struct
import zipfile

import pytest

from app.utils.annex_file import Table, read_annex_file
from app.utils.annex_file.reader import _LIST_HEADER, _PARA_TEXT, _TABLE, _decode_hwp_paragraph, _hwp_blocks


def _units(*codes: int) -> bytes:
    return struct.pack(f"<{len(codes)}H", *codes)


def _chars(text: str) -> bytes:
    return text.encode("utf-16-le")


def _wide(code: int) -> bytes:
    # 8글자 조판 부호: 부호 + 컨트롤 ID 등 6글자 + 같은 부호
    return _units(code, 0x6364, 0x7365, 0, 0, 0, 0, code)


def test_닫는_조판_부호_뒤_글자를_건너뛰지_않는다():
    # 시행규칙 별표 제목: 구역 정의(secd)·단 정의(cold) 부호 뒤에 "■ 어린이제품"
    data = _wide(2) + _wide(2) + _chars("■ 어린이제품") + _units(13)

    assert _decode_hwp_paragraph(data) == "■ 어린이제품"


def test_탭은_공백_줄바꿈은_줄바꿈으로_남긴다():
    data = _chars("분류") + _wide(9) + _chars("품목") + _units(10) + _chars("세부품목") + _units(13)

    assert _decode_hwp_paragraph(data) == "분류 품목\n세부품목"


def _list_header(row: int, col: int, row_span: int = 1, col_span: int = 1) -> bytes:
    return bytes(8) + struct.pack("<HHHH", col, row, col_span, row_span) + bytes(16)


def _cell_records(level: int, row: int, col: int, *texts: str, row_span: int = 1) -> list[tuple[int, int, bytes]]:
    return [(_LIST_HEADER, level, _list_header(row, col, row_span))] + [
        (_PARA_TEXT, level + 1, _chars(text) + _units(13)) for text in texts
    ]


def test_HWP_레코드에서_본문_문단과_병합_칸이_있는_표를_읽는다():
    records = [
        (_PARA_TEXT, 1, _chars("[별표 4]") + _units(13)),
        (_TABLE, 2, bytes(24)),
        *_cell_records(2, 0, 0, "분류"),
        *_cell_records(2, 0, 1, "품목"),
        *_cell_records(2, 1, 0, "2. 생활용품", row_span=2),
        *_cell_records(2, 1, 1, "가. 가스라이터", "(충전식 포함)"),
        *_cell_records(2, 2, 1, "나. 물놀이기구"),
        (_PARA_TEXT, 1, _chars("비고") + _units(13)),
    ]

    blocks = list(_hwp_blocks(records))

    assert blocks[0] == "[별표 4]" and blocks[2] == "비고"
    grid = blocks[1].grid()
    assert [[cell.text for cell in row] for row in grid] == [
        ["분류", "품목"],
        ["2. 생활용품", "가. 가스라이터\n(충전식 포함)"],
        ["2. 생활용품", "나. 물놀이기구"],
    ]


def test_HWP_칸_안_표는_칸이_여럿이면_표로_하나면_글자로_둔다():
    records = [
        (_TABLE, 2, bytes(24)),
        *_cell_records(2, 0, 0, "제목"),
        (_TABLE, 4, bytes(24)),
        *_cell_records(4, 0, 0, "분류"),
        *_cell_records(4, 0, 1, "품목"),
        *_cell_records(2, 1, 0, "비고"),
        (_TABLE, 4, bytes(24)),
        *_cell_records(4, 0, 0, "상자 안 안내"),
    ]

    frame = next(_hwp_blocks(records))

    first, second = frame.cells
    assert first.text == "제목" and [cell.text for cell in first.tables[0].cells] == ["분류", "품목"]
    assert second.content == ("비고", "상자 안 안내")


_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _tc(row: int, col: int, inner: str, row_span: int = 1) -> str:
    return (f'<hp:tc><hp:subList>{inner}</hp:subList><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
            f'<hp:cellSpan colSpan="1" rowSpan="{row_span}"/></hp:tc>')


def _p(text: str, extra: str = "") -> str:
    return f"<hp:p><hp:run><hp:t>{text}</hp:t>{extra}</hp:run></hp:p>"


def _hwpx(body: str) -> bytes:
    section = f'<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="{_HP}">{body}</hs:sec>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        archive.writestr("Contents/section0.xml", section)
    return buffer.getvalue()


def test_HWPX에서_문단과_병합_칸이_있는_표를_읽는다():
    box = f"<hp:tbl>{'<hp:tr>' + _tc(0, 0, _p('산업용 기자재')) + '</hp:tr>'}</hp:tbl>"
    table = (
        "<hp:tbl>"
        f"<hp:tr>{_tc(0, 0, _p('품목'))}{_tc(0, 1, _p('전자파'))}</hp:tr>"
        f"<hp:tr>{_tc(1, 0, _p('1) 무선기기'), row_span=2)}{_tc(1, 1, _p('○'))}</hp:tr>"
        f"<hp:tr>{_tc(2, 1, _p('대표 품목:<hp:lineBreak/>무선 랜카드', box))}</hp:tr>"
        "</hp:tbl>"
    )
    content = _hwpx(_p("[별표 1]") + _p("적합성평가 대상기자재", table))

    blocks = read_annex_file(content, "hwpx")

    assert blocks[:2] == ["[별표 1]", "적합성평가 대상기자재"]
    assert isinstance(blocks[2], Table)
    assert [[cell.text for cell in row] for row in blocks[2].grid()] == [
        ["품목", "전자파"],
        ["1) 무선기기", "○"],
        ["1) 무선기기", "대표 품목:\n무선 랜카드\n산업용 기자재"],
    ]


@pytest.mark.parametrize("content, file_type", [
    (b"%PDF-1.4", "pdf"),
    (b"not a zip", "hwpx"),
    (b"not an ole file", "hwp"),
])
def test_지원하지_않거나_깨진_파일은_오류를_낸다(content, file_type):
    with pytest.raises(ValueError):
        read_annex_file(content, file_type)
