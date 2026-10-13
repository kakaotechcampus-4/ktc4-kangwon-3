"""대상법령·구비요건 표(관세법 제226조 세관장확인물품 고시 별표 1·2)를 푸는 규칙을 별표 모양의 작은 표로 확인한다."""

import pytest

from app.utils.annex_file import Cell, Table
from app.utils.annex_file.requirement_table import is_requirement_table, parse_requirement_tables


def _cell(row: int, col: int, text: str, row_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=1, content=tuple(text.splitlines()))


_HEADER = (_cell(0, 0, "대상법령 및 물품의 범위"), _cell(0, 1, "구비요건"))

# 쪽마다 끊긴 표 두 개: 법률 행이 품목인 경우, 분류인 경우, 한 칸에 법률·(가)가 같이 있는 경우, 병합된 구비요건, 삭제
_FIRST = Table((
    *_HEADER,
    _cell(1, 0, "(1)「마약류 관리에 관한 법률」해당 물품"), _cell(1, 1, "ㅇ식품의약품안전처장의 수출승인(요건확인)서"),
    _cell(2, 0, "(2) (삭제)"), _cell(2, 1, ""),
    _cell(3, 0, "(18)「야생생물 보호 및 관리에 관한 법률」해당 물품(다만, 쉽게 식별할 수 없는 가공품은 제외)"),
    _cell(3, 1, ""),
    _cell(4, 0, "(가)< 삭 제 >"), _cell(4, 1, "ㅇ< 삭 제 >"),
    _cell(5, 0, "(나)멸종위기에 처한 야생생물(국제적 멸종위기종 포함)"),
    _cell(5, 1, "ㅇ유역(지방)환경청장의 수입허가증\nㅇ국립야생동물질병관리원장의 수입검역 증명서"),
))
_SECOND = Table((
    *_HEADER,
    _cell(1, 0, "(41)「생물다양성 보전 및 이용에 관한 법률」해당 물품\n(가)생태계교란 생물"),
    _cell(1, 1, "ㅇ유역(지방)환경청장의 생태계교란 생물 수입허가서"),
    _cell(2, 0, "(45)「에너지이용 합리화법」해당 물품"), _cell(2, 1, ""),
    _cell(3, 0, "(가)삼상유도전동기"), _cell(3, 1, "ㅇ한국에너지공단이사장의 수입 요건 확인서", row_span=2),
    _cell(4, 0, "(나)공기압축기"),
))
_BLOCKS = ["【별표 2】세관장확인대상 수입물품", "가. 대상법령 및 물품의 범위와 구비요건", _FIRST, _SECOND,
           "나. 물품별 수입요건", "(1) HSK 10단위로 연계되지 아니하는 물품의 수입요건", "㉮ <삭제>"]


def _rows(output) -> list[tuple]:
    return [(item.category_path, item.item_label, item.item_name,
             [(attribute.name, attribute.values) for attribute in item.attributes]) for item in output.items]


def test_머리_행이_대상법령과_구비요건인_표를_알아본다():
    assert is_requirement_table(_FIRST)
    assert not is_requirement_table(Table((_cell(0, 0, "분류"), _cell(0, 1, "품목"))))


def test_법률_행은_구비요건이_있으면_품목_없으면_아래_행들의_분류다():
    output = parse_requirement_tables(_BLOCKS)

    assert output.scheme == "세관장확인대상 수입물품"
    assert _rows(output) == [
        ([], "(1)", "「마약류 관리에 관한 법률」해당 물품", [("구비요건", ["식품의약품안전처장의 수출승인(요건확인)서"])]),
        (["(18)「야생생물 보호 및 관리에 관한 법률」해당 물품"], "(나)", "멸종위기에 처한 야생생물",
         [("구비요건", ["유역(지방)환경청장의 수입허가증", "국립야생동물질병관리원장의 수입검역 증명서"])]),
        (["(41)「생물다양성 보전 및 이용에 관한 법률」해당 물품"], "(가)", "생태계교란 생물",
         [("구비요건", ["유역(지방)환경청장의 생태계교란 생물 수입허가서"])]),
        (["(45)「에너지이용 합리화법」해당 물품"], "(가)", "삼상유도전동기",
         [("구비요건", ["한국에너지공단이사장의 수입 요건 확인서"])]),
        (["(45)「에너지이용 합리화법」해당 물품"], "(나)", "공기압축기",
         [("구비요건", ["한국에너지공단이사장의 수입 요건 확인서"])]),
    ]


def test_법률_분류의_괄호_문구는_아래_행들에_붙인다():
    item = parse_requirement_tables(_BLOCKS).items[1]

    assert (item.exclusions, item.inclusions) == (["다만, 쉽게 식별할 수 없는 가공품은 제외"], ["국제적 멸종위기종 포함"])


def test_삭제는_뺀_행으로_표_뒤_문단은_비고로_둔다():
    output = parse_requirement_tables(_BLOCKS)

    assert [(row.item_label, row.reason) for row in output.skipped] == [("(2)", "(삭제)"), ("(가)", "< 삭 제 >")]
    assert output.notes == ["(1) HSK 10단위로 연계되지 아니하는 물품의 수입요건"]


def test_대상법령_구비요건_표가_아니면_오류를_낸다():
    with pytest.raises(ValueError):
        parse_requirement_tables(["제목", Table((_cell(0, 0, "분류"), _cell(0, 1, "품목")))])
