"""별표 원본 파일 표 모양에 맞는 규칙을 골라 품목 행으로 푼다."""

from ...schemas.annex import AnnexParseOutput
from .category_table import is_category_table, parse_category_table
from .grid import Block, Table
from .matrix_table import is_matrix_table, parse_matrix_tables
from .requirement_table import is_requirement_table, parse_requirement_tables
from .row_table import parse_row_table


def parse_annex(blocks: list[Block]) -> tuple[str, AnnexParseOutput]:
    """표 모양으로 규칙을 고른다.

    - 모든 표가 대상법령·구비요건 표 → requirement (관세 고시)
    - 모든 표가 ○ 표시 행렬 → matrix (전파 고시)
    - 첫 표가 분류·품목·세부품목 → category (운용요령)
    - 표가 하나 → row (시행규칙·어린이·전파법 시행령)

    Args:
        blocks: 별표 원본 파일의 문단·표 (read_annex_file 결과).

    Returns:
        tuple[str, AnnexParseOutput]: (고른 규칙 이름, 파싱 결과).

    Raises:
        ValueError: 맞는 규칙이 없거나 규칙이 표를 풀지 못한 경우.
    """
    tables = [block for block in blocks if isinstance(block, Table)]
    if not tables:
        raise ValueError("별표 파일에 표가 없습니다.")
    if all(is_requirement_table(table) for table in tables):
        return "requirement", parse_requirement_tables(blocks)
    if all(is_matrix_table(table) for table in tables):
        return "matrix", parse_matrix_tables(blocks)
    if is_category_table(tables[0]):
        return "category", parse_category_table(blocks)
    if len(tables) == 1:
        return "row", parse_row_table(blocks)
    raise ValueError(f"표 모양에 맞는 규칙이 없습니다 (표 {len(tables)}개).")
