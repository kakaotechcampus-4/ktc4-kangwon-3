"""별표 원본 파일의 표를 칸 주소·병합 그대로 담는 격자 모델. 순수 자료구조만 둠."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    """표의 칸 하나. 병합된 칸은 왼쪽 위 주소에 한 번만 있음.

    Attributes:
        row: 행 주소 (0부터).
        col: 열 주소 (0부터).
        row_span: 아래로 합쳐진 행 수.
        col_span: 오른쪽으로 합쳐진 열 수.
        content: 칸 안 문단 글자(str)와 칸이 여럿인 표(Table)를 순서대로. 칸 하나짜리 표(상자)는 글자로 풀어 넣음.
    """

    row: int
    col: int
    row_span: int
    col_span: int
    content: tuple["Block", ...] = ()

    @property
    def text(self) -> str:
        """칸 안 문단 글자를 줄바꿈으로 이은 것. 칸 안 표 글자는 뺌."""
        return "\n".join(block for block in self.content if isinstance(block, str))

    @property
    def tables(self) -> tuple["Table", ...]:
        """칸 안 표."""
        return tuple(block for block in self.content if isinstance(block, Table))


@dataclass(frozen=True)
class Table:
    """칸 목록으로 이루어진 표.

    Attributes:
        cells: 원본 순서의 칸 목록.
    """

    cells: tuple[Cell, ...] = ()

    @property
    def row_count(self) -> int:
        """병합을 펼친 행 수."""
        return max((cell.row + cell.row_span for cell in self.cells), default=0)

    @property
    def col_count(self) -> int:
        """병합을 펼친 열 수."""
        return max((cell.col + cell.col_span for cell in self.cells), default=0)

    def grid(self) -> list[list[Cell | None]]:
        """병합을 펼친 격자를 만든다. 병합된 자리마다 같은 칸을 가리킴.

        Returns:
            list[list[Cell | None]]: 행·열 격자. 어느 칸도 덮지 않는 자리는 None.
        """
        grid: list[list[Cell | None]] = [[None] * self.col_count for _ in range(self.row_count)]
        for cell in self.cells:
            for row in range(cell.row, cell.row + cell.row_span):
                for col in range(cell.col, cell.col + cell.col_span):
                    grid[row][col] = cell
        return grid


# 파일 본문 순서의 문단 글자(str)와 표
Block = str | Table


def unwrap_frames(blocks: list[Block]) -> list[Block]:
    """칸 안에 표를 둔 틀 표를 벗겨, 칸 내용을 본문 순서대로 꺼낸다.

    시행규칙 별표 일부는 제목·본문 표·비고를 바깥 표(틀) 칸에 넣어 둠. 틀을 벗기면 다른 별표처럼
    문단과 표가 나란한 모양이 됨.

    Args:
        blocks: 본문 순서의 문단 글자와 표.

    Returns:
        list[Block]: 틀 표를 칸 내용으로 바꾼 목록. 칸 안 문단 글자는 줄마다 나눔.
    """
    unwrapped: list[Block] = []
    for block in blocks:
        if isinstance(block, Table) and any(cell.tables for cell in block.cells):
            for cell in block.cells:
                for inner in unwrap_frames(list(cell.content)):
                    unwrapped.extend(inner.splitlines() if isinstance(inner, str) else [inner])
        else:
            unwrapped.append(block)
    return unwrapped
