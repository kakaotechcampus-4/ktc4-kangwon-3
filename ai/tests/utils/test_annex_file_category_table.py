"""분류·품목·세부품목 표(운용요령 별표)를 품목 행으로 푸는 규칙을 별표 모양의 작은 표로 확인한다."""

import pytest

from app.utils.annex_file import Cell, Table
from app.utils.annex_file.category_table import is_category_table, parse_category_table


def _cell(row: int, col: int, text: str, row_span: int = 1, col_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=col_span, content=tuple(text.splitlines()))


_HEADER = (_cell(0, 0, "분류"), _cell(0, 1, "품 목"), _cell(0, 2, "세부품목"))

# 운용요령 별표 1 모양: 분류 묶음 비고(2~3열 병합), 품목 묶음 비고(3열), 삭제, 대상 없음, 표 전체 비고
_TABLE = Table((
    *_HEADER,
    _cell(1, 0, "1. 전선 및 전원코드", row_span=2),
    _cell(1, 1, "전선, 케이블 및\n코드류"),
    _cell(1, 2, "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)\n② 삭제<2023. 3. 20.>\n③ 코드세트"),
    _cell(2, 1, "비고: 교류전압을 사용하는 제품에 한정하며, 통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다.",
          col_span=2),
    _cell(3, 0, "7. 전기기기\n7. 전기기기", row_span=4),
    _cell(3, 1, "가. 삭제<2026.4.1>"),
    _cell(3, 2, ""),
    _cell(4, 1, "자. 전기담요(전기침대를 포함한다)", row_span=2),
    _cell(4, 2, "① 전기요\n② 전기매트"),
    _cell(5, 2, "비고: 교류전원 30V 이하에서 사용\n하는 것을 포함한다."),
    _cell(6, 1, "터. 그 밖에 가목과 유사한 기기", col_span=2),
    _cell(7, 0, "9. 오디오·비디오"),
    _cell(7, 1, "대상 없음", col_span=2),
    _cell(8, 0, "비고: 1차 전지(건전지)만을 전원으로 사용하는 구조의 것은 제외한다.", col_span=3),
))
_BLOCKS = ["[별표 1]", "안전인증대상전기용품 세부품목(제3조 관련)", _TABLE]


def _rows(output) -> list[tuple]:
    return [(item.category_path, item.item_label, item.item_name, item.conditions, item.exclusions, item.inclusions)
            for item in output.items]


def test_머리_행이_분류_품목_세부품목인_표를_알아본다():
    assert is_category_table(_TABLE)
    assert not is_category_table(Table((_cell(0, 0, "품목"), _cell(0, 1, "적용 안전기준"))))


def test_세부품목_번호_줄마다_행_하나에_괄호_문구와_분류_묶음_비고를_붙인다():
    output = parse_category_table(_BLOCKS)

    assert output.scheme == "안전인증대상전기용품"
    assert _rows(output)[:2] == [
        (["1. 전선 및 전원코드", "전선, 케이블 및 코드류"], "①", "절연전선",
         ["공칭단면적이 95mm2 이하인 것에 한정한다", "교류전압을 사용하는 제품에 한정하며"],
         ["통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다."], []),
        (["1. 전선 및 전원코드", "전선, 케이블 및 코드류"], "③", "코드세트",
         ["교류전압을 사용하는 제품에 한정하며"], ["통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다."], []),
    ]
    assert output.items[0].source_text == "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)"


def test_품목_칸_괄호와_품목_묶음_비고는_그_품목의_행에만_붙인다():
    rows = _rows(parse_category_table(_BLOCKS))

    assert rows[2:4] == [
        (["7. 전기기기", "자. 전기담요"], "①", "전기요", [], [],
         ["전기침대를 포함한다", "교류전원 30V 이하에서 사용 하는 것을 포함한다."]),
        (["7. 전기기기", "자. 전기담요"], "②", "전기매트", [], [],
         ["전기침대를 포함한다", "교류전원 30V 이하에서 사용 하는 것을 포함한다."]),
    ]


def test_세부품목_없이_두_칸에_걸친_품목은_품목이_행이다():
    assert _rows(parse_category_table(_BLOCKS))[4] == (["7. 전기기기"], "터.", "그 밖에 가목과 유사한 기기", [], [], [])


def test_삭제와_대상_없음은_뺀_행으로_표_전체_비고는_notes로_둔다():
    output = parse_category_table(_BLOCKS)

    assert [(row.item_label, row.reason) for row in output.skipped] == [
        ("②", "삭제<2023. 3. 20.>"), ("가.", "삭제<2026.4.1>"), (None, "대상 없음")]
    assert output.notes == ["1차 전지(건전지)만을 전원으로 사용하는 구조의 것은 제외한다."]


def test_다음_문단으로_넘어간_품목은_잇고_번호가_빠진_품목은_따로_둔다():
    table = Table((
        *_HEADER,
        _cell(1, 0, "11. 조명기기"),
        _cell(1, 1, "나. 일반조명기구"),
        _cell(1, 2, "① 종합유선방송 가입자 단말장치\n(디지털 CATV용 셋톱박스 등)\n"
                    "⑥ 고압방전등기구(램프당 150W 이하인 것에 한정함)\n투광조명기구"),
    ))

    output = parse_category_table(["제목", table])

    assert [(item.item_label, item.item_name) for item in output.items] == [
        ("①", "종합유선방송 가입자 단말장치 (디지털 CATV용 셋톱박스 등)"),
        ("⑥", "고압방전등기구"),
        (None, "투광조명기구"),
    ]


def test_품목_칸과_세부품목_칸이_같으면_품목은_분류_단계가_아니다():
    # 운용요령 별표 3의2 모양
    detail = "① 재사용전지모듈\n② 재사용전지시스템(정격용량이 300kWh 이하인 것만 해당한다)"
    table = Table((*_HEADER, _cell(1, 0, "1. 재사용전지"), _cell(1, 1, detail), _cell(1, 2, detail)))

    rows = _rows(parse_category_table(["제목", table]))

    assert rows == [
        (["1. 재사용전지"], "①", "재사용전지모듈", [], [], []),
        (["1. 재사용전지"], "②", "재사용전지시스템", ["정격용량이 300kWh 이하인 것만 해당한다"], [], []),
    ]


def test_분류_품목_세부품목_표가_아니면_오류를_낸다():
    with pytest.raises(ValueError):
        parse_category_table(["제목", Table((_cell(0, 0, "품목"), _cell(0, 1, "적용 안전기준")))])
