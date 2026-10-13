"""○ 표시 행렬 표(방송통신기자재 적합성평가 고시 별표 1)를 푸는 규칙을 별표 모양의 작은 표로 확인한다."""

import pytest

from app.utils.annex_file import Cell, Table
from app.utils.annex_file.matrix_table import is_matrix_table, parse_matrix_tables


def _cell(row: int, col: int, text: str, row_span: int = 1, col_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=col_span, content=tuple(text.splitlines()))


def _attributes(item) -> list[tuple[str, list[str]]]:
    return [(attribute.name, attribute.values) for attribute in item.attributes]


# 고시 별표 1 표 1~10 모양: 머리글 3단, 품목 열 2개, ○ 열 4개(셋째 단 있는 열 포함), 기기부호
_HEADER = (
    _cell(0, 0, "대상기자재", row_span=3, col_span=2),
    _cell(0, 2, "적합성평가기준 적용분야", col_span=2), _cell(0, 4, "적합성평가 유형", col_span=2),
    _cell(0, 6, "기기\n부호", row_span=3),
    _cell(1, 2, "무선", row_span=2), _cell(1, 3, "전자파\n인체보호"),
    _cell(1, 4, "적합\n인증", row_span=2), _cell(1, 5, "적합\n등록", row_span=2),
    _cell(2, 3, "전자파\n흡수율"),
)


def _marks(row: int, *marks: str) -> tuple[Cell, ...]:
    return tuple(_cell(row, 2 + index, mark) for index, mark in enumerate(marks))


_RADIO = Table((
    *_HEADER,
    _cell(3, 0, "가.디지털선택호출 장치의 기기", row_span=2), _cell(3, 1, "1)선박국용"),
    *_marks(3, "○", "", "○", ""), _cell(3, 6, "SA"),
    _cell(4, 1, "2)해안국용"), *_marks(4, "○", "○", "", "○"), _cell(4, 6, "SB"),
    _cell(5, 0, "나.네비텍스수신기", col_span=2), *_marks(5, "○", "", "○", ""), _cell(5, 6, "NR"),
))


def test_머리글_아래_동그라미만_있는_열이_있으면_행렬_표다():
    assert is_matrix_table(_RADIO)
    assert not is_matrix_table(Table((_cell(0, 0, "분류"), _cell(0, 1, "품목"), _cell(1, 0, "가. 화학"),
                                      _cell(1, 1, "건전지"))))


def test_동그라미_열을_위_단_머리글별로_묶고_셋째_단은_괄호로_붙인다():
    output = parse_matrix_tables(["[별표 1]", "적합성평가 대상기자재", "(제3조 관련)", "1. 해상업무용 무선설비의 기기",
                                  _RADIO])

    assert output.scheme == "적합성평가 대상기자재"
    first, second, third = output.items
    assert (first.category_path, first.item_label, first.item_name) == (
        ["1. 해상업무용 무선설비의 기기", "가.디지털선택호출 장치의 기기"], "1)", "선박국용")
    assert _attributes(first) == [("적합성평가기준 적용분야", ["무선"]), ("적합성평가 유형", ["적합인증"]),
                                  ("기기부호", ["SA"])]
    assert _attributes(second)[:2] == [("적합성평가기준 적용분야", ["무선", "전자파인체보호(전자파흡수율)"]),
                                       ("적합성평가 유형", ["적합등록"])]
    assert (third.category_path, third.item_label, third.item_name) == (
        ["1. 해상업무용 무선설비의 기기"], "나.", "네비텍스수신기")


# 고시 별표 1 표 11 모양: 대·중·소분류, 설명 칸, "o …" 추가 행, ○ 열을 가로지르는 제외 조항, 표 끝 비고
_HOME = Table((
    _cell(0, 0, "대상기자재", col_span=3), _cell(0, 3, "적합성평가 유형", col_span=2),
    _cell(0, 5, "기기\n부호", row_span=2),
    _cell(1, 0, "대분류"), _cell(1, 1, "중분류"), _cell(1, 2, "소분류"),
    _cell(1, 3, "적합\n등록"), _cell(1, 4, "자기\n적합\n확인"),
    _cell(2, 0, "나.생활가전기기류\n: 생활 환경에서 주로 사용되는 전기기기", row_span=4),
    _cell(2, 1, "1) 전기청소기류", row_span=2),
    _cell(2, 2, "o (정의) 바닥청소를 하는 기기\no 대표적인 품목은 다음과 같다.\n"
                "- 진공청소기, 물흡입청소기(물걸레청소기 포함), 로봇청소기 등"),
    _cell(2, 3, "○"), _cell(2, 4, ""), _cell(2, 5, "CLN11"),
    _cell(3, 2, "o 전동기의 정격입력이 2.5 kW를 초과하는 기기"),
    _cell(3, 3, ""), _cell(3, 4, "○"), _cell(3, 5, "CLN12"),
    _cell(4, 1, "34) 기타 가정·상업용 전기기기"), _cell(4, 2, "① 보풀제거기"),
    _cell(4, 3, ""), _cell(4, 4, "○"), _cell(4, 5, "CLE12"),
    _cell(5, 1, "35) 생활 가전기기류 중 다음의 어느 하나에 해당하는 기자재는 적합성평가 대상에서 제외한다.\n"
                "o 의료기기법 제2조제1항에 따른 의료기기인 것", col_span=5),
    _cell(6, 0, "※ 비 고\n1. 대표적인 품목은 보편적인 대상 명칭을 나열한 것이다.", col_span=6),
))


def _home_output():
    return parse_matrix_tables(["적합성평가 대상기자재", "11. 전자파장해를 주거나 전자파로부터 영향을 받는 기기", _HOME])


def test_설명_칸이_있으면_왼쪽_칸이_품목이고_정의와_대표_품목은_추가_칸이다():
    item = _home_output().items[0]

    assert (item.category_path, item.item_label, item.item_name) == (
        ["11. 전자파장해를 주거나 전자파로부터 영향을 받는 기기", "나.생활가전기기류"], "1)", "전기청소기류")
    assert _attributes(item) == [
        ("정의", ["바닥청소를 하는 기기"]),
        ("대표 품목", ["진공청소기", "물흡입청소기(물걸레청소기 포함)", "로봇청소기"]),
        ("적합성평가 유형", ["적합등록"]),
        ("기기부호", ["CLN11"]),
    ]


def test_자기_동그라미를_가진_o_줄은_위_품목_아래_추가_행이다():
    item = _home_output().items[1]

    assert (item.category_path[-1], item.item_label, item.item_name) == (
        "1) 전기청소기류", None, "전동기의 정격입력이 2.5 kW를 초과하는 기기")
    assert _attributes(item) == [("적합성평가 유형", ["자기적합확인"]), ("기기부호", ["CLN12"])]


def test_동그라미_열을_가로지른_제외_조항은_묶음_행들의_제외_문구가_되고_번호는_뺀_행으로_남긴다():
    output = _home_output()

    assert all(item.exclusions == ["생활 가전기기류 중 다음의 어느 하나에 해당하는 기자재는 적합성평가 대상에서 제외한다.",
                                   "의료기기법 제2조제1항에 따른 의료기기인 것"] for item in output.items)
    assert [(row.item_label, row.reason) for row in output.skipped] == [
        ("35)", "생활 가전기기류 중 다음의 어느 하나에 해당하는 기자재는 적합성평가 대상에서 제외한다.")]
    assert output.notes == ["대표적인 품목은 보편적인 대상 명칭을 나열한 것이다."]


def test_분류_칸의_설명_줄은_분류_이름에서_뺀다():
    assert _home_output().items[2].category_path[1:] == ["나.생활가전기기류", "34) 기타 가정·상업용 전기기기"]


def test_행렬_표가_아니면_오류를_낸다():
    with pytest.raises(ValueError):
        parse_matrix_tables(["제목", Table((_cell(0, 0, "분류"), _cell(0, 1, "품목")))])


def test_번호_칸_안의_정의와_대표_품목은_설명_칸으로_읽고_삭제_행은_뺀다():
    # 고시 별표 1 표 11 "① 컴퓨터 및 컴퓨터 시스템 ⏎ o (정의) …", 표 7 "27) (삭 제)" 모양
    table = Table((
        _cell(0, 0, "대상기자재", col_span=2), _cell(0, 2, "적합\n등록"), _cell(0, 3, "기기\n부호"),
        _cell(1, 0, "1) 정보기기류", row_span=3),
        _cell(1, 1, "① 컴퓨터 및 컴퓨터 시스템\no (정의) 중앙처리장치를 가진 전자 컴퓨터\n"
                    "o 대표적인 품목은 다음과 같다.\n- 데스크톱, 노트북"),
        _cell(1, 2, "○"), _cell(1, 3, "ITE11"),
        _cell(2, 1, "② 전기분무기(교류전원 사용기기에 한함)"), _cell(2, 2, "○"), _cell(2, 3, "ITE12"),
        _cell(3, 1, "27) (삭 제)"), _cell(3, 2, ""), _cell(3, 3, ""),
    ))

    output = parse_matrix_tables(["적합성평가 대상기자재", table])

    first, second = output.items
    assert (first.item_label, first.item_name) == ("①", "컴퓨터 및 컴퓨터 시스템")
    assert _attributes(first)[:2] == [("정의", ["중앙처리장치를 가진 전자 컴퓨터"]), ("대표 품목", ["데스크톱", "노트북"])]
    assert (second.item_name, second.conditions) == ("전기분무기", ["교류전원 사용기기에 한함"])
    assert [(row.item_label, row.reason) for row in output.skipped] == [("27)", "(삭 제)")]


def test_품목_칸_아래_단서_칸은_그_품목_행에_붙인다():
    # 고시 별표 1 표 11 "8) 전열기구류" 아래 "o 다음에 해당하는 기자재는 … 제외한다." 모양
    table = Table((
        _cell(0, 0, "대상기자재", col_span=3), _cell(0, 3, "적합\n등록"), _cell(0, 4, "기기\n부호"),
        _cell(1, 0, "나.생활가전기기류", row_span=2),
        _cell(1, 1, "8) 전열기구류", row_span=2), _cell(1, 2, "o (정의) 난방을 하는 기기"),
        _cell(1, 3, "○"), _cell(1, 4, "HEA11"),
        _cell(2, 2, "o 다음에 해당하는 기자재는 적합성평가 대상에서 제외한다.\n- 단순 열선으로만 구성되어 있는 전기가열기기",
              col_span=3),
    ))

    item = parse_matrix_tables(["적합성평가 대상기자재", table]).items[0]

    assert (item.item_name, item.exclusions) == ("전열기구류", [
        "다음에 해당하는 기자재는 적합성평가 대상에서 제외한다.", "단순 열선으로만 구성되어 있는 전기가열기기"])
