"""별표 표 격자 모델이 병합 칸을 펼치고 틀 표를 벗기는지 확인한다."""

from app.utils.annex_file import Cell, Table
from app.utils.annex_file.grid import unwrap_frames


def _cell(row: int, col: int, *content, row_span: int = 1, col_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=col_span, content=content)


# 운용요령 별표 4 모양: 분류 칸이 품목 두 행에 걸쳐 병합
_TABLE = Table((
    _cell(0, 0, "분류"), _cell(0, 1, "품목"),
    _cell(1, 0, "2. 생활용품", row_span=2), _cell(1, 1, "가. 가스라이터"),
    _cell(2, 1, "나. 물놀이기구"),
    _cell(3, 0, "비고: 전부 해당", col_span=2),
))


def test_병합된_칸을_덮는_자리마다_펼친다():
    grid = _TABLE.grid()

    assert (_TABLE.row_count, _TABLE.col_count) == (4, 2)
    assert [row[0].text for row in grid] == ["분류", "2. 생활용품", "2. 생활용품", "비고: 전부 해당"]
    assert grid[3][0] is grid[3][1]


def test_칸_글자는_문단을_줄로_잇고_칸_안_표는_따로_둔다():
    cell = _cell(0, 0, "① 가스라이터", _TABLE, "② 라이터 충전기")

    assert cell.text == "① 가스라이터\n② 라이터 충전기"
    assert cell.tables == (_TABLE,)


def test_칸_안에_표를_둔_틀_표는_칸_내용을_순서대로_꺼낸다():
    # 시행규칙 별표 7의2 모양: 틀 칸에 제목, 본문 표, 비고
    frame = Table((
        _cell(0, 0, "■ 시행규칙 [별표 7의2]\n안전성검사대상전기용품"),
        _cell(1, 0, _TABLE, "비고"),
    ))

    assert unwrap_frames(["앞 문단", frame]) == ["앞 문단", "■ 시행규칙 [별표 7의2]", "안전성검사대상전기용품", _TABLE, "비고"]


def test_칸_안에_표가_없는_표는_그대로_둔다():
    assert unwrap_frames([_TABLE]) == [_TABLE]
