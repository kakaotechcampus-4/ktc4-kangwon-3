"""별표 표 모양에 맞는 규칙을 고르는지 확인한다."""

import pytest

from app.utils.annex_file import Cell, Table, parse_annex


def _table(*rows: tuple[str, ...]) -> Table:
    return Table(tuple(Cell(row=row, col=col, row_span=1, col_span=1, content=(text,) if text else ())
                       for row, texts in enumerate(rows) for col, text in enumerate(texts)))


@pytest.mark.parametrize("blocks, rule", [
    (["[별표 4]", "안전인증대상생활용품 세부품목(제3조 관련)",
      _table(("분류", "품목", "세부품목"), ("1. 화학", "자동차용 재생타이어", "① 자동차용 재생타이어"))], "category"),
    (["【별표 2】세관장확인대상 수입물품",
      _table(("대상법령 및 물품의 범위", "구비요건"), ("(23)「화장품법」해당 물품", "ㅇ표준통관예정보고서")),
      _table(("대상법령 및 물품의 범위", "구비요건"), ("(37)「계량에 관한 법률」해당 물품", "ㅇ형식승인확인서"))],
     "requirement"),
    (["적합성평가 대상기자재", _table(("대상기자재", "무선", "기기부호"), ("가.네비텍스수신기", "○", "NR"))], "matrix"),
    (["안전기준준수대상생활용품(제3조제7항 관련)", _table(("분류", "품목"), ("가. 화학", "1) 가죽제품"))], "row"),
])
def test_표_모양으로_규칙을_고른다(blocks, rule):
    chosen, output = parse_annex(blocks)

    assert chosen == rule
    assert output.items


def test_맞는_규칙이_없으면_오류를_낸다():
    with pytest.raises(ValueError):
        parse_annex(["표 없는 별표"])
    with pytest.raises(ValueError):
        parse_annex(["제목", _table(("분류", "품목"), ("가", "나")), _table(("분류", "품목"), ("다", "라"))])
