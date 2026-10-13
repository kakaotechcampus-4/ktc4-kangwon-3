"""품목이 행마다 놓인 별표 표(시행규칙 대상제품, 어린이제품 적용 안전기준, 전파법 면제대상)를 푸는 규칙을 확인한다."""

import pytest

from app.utils.annex_file import Cell, Table
from app.utils.annex_file.row_table import parse_row_table


def _cell(row: int, col: int, text: str, row_span: int = 1, col_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=col_span, content=tuple(text.splitlines()))


def _rows(output) -> list[tuple]:
    return [(item.category_path, item.item_label, item.item_name, item.conditions, item.exclusions, item.inclusions)
            for item in output.items]


# 전기 시행규칙 별표 3 모양: 표 안 제목·구간, 분류(2열 병합)·품목, 품목 열 묶음 비고, 구간마다 열 이름 행
_RULE_TABLE = Table((
    _cell(0, 0, "안전인증대상제품(제3조제1항 및 제2항 관련)\n1. 안전인증대상전기용품", col_span=3),
    _cell(1, 0, "분류", col_span=2), _cell(1, 2, "품목"),
    _cell(2, 0, "나. 전기기기용 스위치", row_span=2, col_span=2),
    _cell(2, 2, "1) 스위치\n2) 전자개폐기(정격전류가 300A 이하인 것을 말한다)"),
    _cell(3, 2, "비고) 교류전압을 사용하는 제품으로 한정하며, 방폭형인 것은 제외한다."),
    _cell(4, 0, "사. 전기기기", col_span=2),
    _cell(4, 2, "1) 전기청소기\n6) 삭제 <2018. 12. 31.>\n9) 전기담요 및 매트(전기침대는 제외한다)"),
    _cell(5, 0, "아. 전동공구", col_span=2), _cell(5, 2, "대상 없음"),
    _cell(6, 0, "2. 안전인증대상생활용품", col_span=3),
    _cell(7, 0, "분류"), _cell(7, 1, "품목", col_span=2),
    _cell(8, 0, "가. 화학"), _cell(8, 1, "자동차용 재생타이어(트레드고무를 포함한다)", col_span=2),
))


def test_표_안_제목에서_규제_구분을_구간은_분류_첫_단계로_둔다():
    output = parse_row_table(["■ 전기용품 및 생활용품 안전관리법 시행규칙 [별표 3]", _RULE_TABLE])

    assert output.scheme == "안전인증대상제품"
    assert _rows(output) == [
        (["1. 안전인증대상전기용품", "나. 전기기기용 스위치"], "1)", "스위치",
         ["교류전압을 사용하는 제품으로 한정하며"], ["방폭형인 것은 제외한다."], []),
        (["1. 안전인증대상전기용품", "나. 전기기기용 스위치"], "2)", "전자개폐기(정격전류가 300A 이하인 것을 말한다)",
         ["교류전압을 사용하는 제품으로 한정하며"], ["방폭형인 것은 제외한다."], []),
        (["1. 안전인증대상전기용품", "사. 전기기기"], "1)", "전기청소기", [], [], []),
        (["1. 안전인증대상전기용품", "사. 전기기기"], "9)", "전기담요 및 매트", [], ["전기침대는 제외한다"], []),
        (["2. 안전인증대상생활용품", "가. 화학"], None, "자동차용 재생타이어", [], [], ["트레드고무를 포함한다"]),
    ]
    assert [(row.item_label, row.reason) for row in output.skipped] == [
        ("6)", "삭제 <2018. 12. 31.>"), (None, "대상 없음")]


def test_품목이_첫_열이면_나머지_열은_추가_칸으로_줄마다_값_하나를_둔다():
    # 어린이제품 시행규칙 별표 3 모양: 마지막 전체 폭 행은 비고
    table = Table((
        _cell(0, 0, "공급자적합성확인대상어린이제품의 종류 및 적용 안전기준(제2조제3항 관련)", col_span=2),
        _cell(1, 0, "공급자적합성확인대상어린이제품"), _cell(1, 1, "적용 안전기준"),
        _cell(2, 0, "가. 어린이용 안경테(선글라스를 포함한다)"),
        _cell(2, 1, "1) 어린이제품 공통안전기준\n2) 어린이용 안경테 안전기준"),
        _cell(3, 0, "나. 삭제 <2018. 4. 19.>"), _cell(3, 1, ""),
        _cell(4, 0, "2. 개별 안전기준이 없는 제품은 어린이제품 공통안전기준을 적용한다.", col_span=2),
    ))

    output = parse_row_table(["■ 어린이제품 안전 특별법 시행규칙 [별표 3]", table])

    assert output.scheme == "공급자적합성확인대상어린이제품"
    item = output.items[0]
    assert (item.item_label, item.item_name, item.inclusions) == ("가.", "어린이용 안경테", ["선글라스를 포함한다"])
    assert [(attribute.name, attribute.values) for attribute in item.attributes] == [
        ("적용 안전기준", ["1) 어린이제품 공통안전기준", "2) 어린이용 안경테 안전기준"])]
    assert [(row.item_label, row.reason) for row in output.skipped] == [("나.", "삭제 <2018. 4. 19.>")]
    assert output.notes == ["개별 안전기준이 없는 제품은 어린이제품 공통안전기준을 적용한다."]


def test_앞_열이_빈_표와_병합된_추가_칸과_단서_문장을_읽는다():
    # 전파법 시행령 별표 6의2 모양: 첫 열이 비고, 면제 내용 칸이 여러 행에 병합
    table = Table((
        _cell(0, 0, "적합성평가 면제대상 기자재(제77조의7제1항 관련)", col_span=4),
        _cell(1, 0, "1. 법 제58조의3제1항제1호에 따른 적합성평가 면제대상 기자재", col_span=4),
        _cell(2, 0, ""), _cell(2, 1, "면제대상 기자재"), _cell(2, 2, "면제 수량"), _cell(2, 3, "면제 내용"),
        _cell(3, 0, ""), _cell(3, 1, "마. 국내 시장조사를 목적으로 수입하는 견본품용 기자재"), _cell(3, 2, "3대"),
        _cell(3, 3, "적합인증, 적합등록 및 자기적합확인", row_span=2),
        _cell(4, 0, ""), _cell(4, 1, "자. 개인이 사용할 목적으로 반입하는 기자재. 다만, 반입일부터 1년 이내에 판매하는 경우는 제외한다."),
        _cell(4, 2, "1대"),
    ))

    output = parse_row_table(["■ 전파법 시행령 [별표 6의2]", table])

    assert output.scheme == "적합성평가 면제대상 기자재"
    second = output.items[1]
    assert (second.item_label, second.item_name, second.exclusions) == (
        "자.", "개인이 사용할 목적으로 반입하는 기자재", ["다만, 반입일부터 1년 이내에 판매하는 경우는 제외한다."])
    assert [[(attribute.name, attribute.values) for attribute in item.attributes] for item in output.items] == [
        [("면제 수량", ["3대"]), ("면제 내용", ["적합인증, 적합등록 및 자기적합확인"])],
        [("면제 수량", ["1대"]), ("면제 내용", ["적합인증, 적합등록 및 자기적합확인"])],
    ]


def test_표_뒤_비고_문단은_번호_항목마다_표_전체_비고로_둔다():
    # 전기 시행규칙 별표 7의2 모양: 제목은 문단, 비고는 표 뒤 문단
    table = Table((_cell(0, 0, "분류"), _cell(0, 1, "품목"), _cell(1, 0, "재사용전지"), _cell(1, 1, "1) 재사용전지모듈")))
    blocks = ["■ 시행규칙 [별표 7의2]", "안전성검사대상전기용품(제3조제9항 관련)", table,
              "비고", "1. 다음 용도로 사용된 것으로 한정한다.", "가. 리튬이차전지시스템", "2. 재사용전지를 포함한다."]

    output = parse_row_table(blocks)

    assert output.scheme == "안전성검사대상전기용품"
    assert _rows(output) == [(["재사용전지"], "1)", "재사용전지모듈", [], [], [])]
    assert output.notes == ["다음 용도로 사용된 것으로 한정한다. 가. 리튬이차전지시스템", "재사용전지를 포함한다."]


def test_표가_하나가_아니면_오류를_낸다():
    with pytest.raises(ValueError):
        parse_row_table(["제목", _RULE_TABLE, _RULE_TABLE])
