"""별표 규칙 파서 결과를 원본과 거꾸로 대조하는 점검이 빠진 줄·번호·비고를 잡는지 확인한다."""

from app.eval.annex_file_audit import audit_annex
from app.utils.annex_file import Cell, Table, parse_annex


def _cell(row: int, col: int, text: str, row_span: int = 1, col_span: int = 1) -> Cell:
    return Cell(row=row, col=col, row_span=row_span, col_span=col_span, content=tuple(text.splitlines()))


# 운용요령 별표 1 모양: 분류 묶음 비고, 대상 없음, 표 전체 비고
_BLOCKS = ["[별표 1]", "안전인증대상전기용품 세부품목(제3조 관련)", Table((
    _cell(0, 0, "분류"), _cell(0, 1, "품 목"), _cell(0, 2, "세부품목"),
    _cell(1, 0, "1. 전선 및 전원코드", row_span=2),
    _cell(1, 1, "전선, 케이블 및\n코드류"),
    _cell(1, 2, "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)\n② 코드세트"),
    _cell(2, 1, "비고: 교류전압을 사용하는 제품에 한정하며, 통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다.",
          col_span=2),
    _cell(3, 0, "9. 오디오·비디오"), _cell(3, 1, "대상 없음", col_span=2),
    _cell(4, 0, "비고: 1차 전지(건전지)만을 전원으로 사용하는 구조의 것은 제외한다.", col_span=3),
))]


def _output():
    return parse_annex(_BLOCKS)[1]


def test_규칙_파서_결과는_점검에_걸리지_않는다():
    assert audit_annex(_BLOCKS, _output()) == {"빠진 줄": [], "빠진 번호 줄": [], "안 붙은 비고": []}


def test_빠진_품목은_빠진_줄과_빠진_번호_줄로_잡는다():
    output = _output()
    output.items = [item for item in output.items if item.item_name != "코드세트"]

    found = audit_annex(_BLOCKS, output)

    assert found["빠진 줄"] == ["표0 칸1,2: ② 코드세트"]
    assert found["빠진 번호 줄"] == ["표0 칸1,2: ② 코드세트"]


def test_묶음_안_행에_비고_문구가_하나라도_빠지면_잡는다():
    output = _output()
    output.items[1].exclusions = []

    assert audit_annex(_BLOCKS, output)["안 붙은 비고"] == [
        "표0 칸2,1 '통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한' → ② 코드세트"]


def test_대상_없음_행의_분류가_빠지면_잡는다():
    output = _output()
    output.skipped[0].category_path = []

    assert audit_annex(_BLOCKS, output)["빠진 줄"] == ["표0 칸3,0: 9. 오디오·비디오"]
