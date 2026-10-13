"""별표 파싱 결과의 원문 대조(문구·번호)를 별표 원문 모양의 짧은 표로 확인한다."""

import pytest

from app.schemas.annex import AnnexAttribute, AnnexItem, AnnexParseOutput, AnnexSkippedRow
from app.utils.annex_check import _haystacks, check_annex, contains, normalize, source_labels

# 운용요령 별표 형식을 줄인 표. 분류 칸 글자가 두 줄로 나뉘고, 묶음 비고와 표 전체 비고가 있음
_TABLE = """\
┏━━━━━━━━━━┯━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━┓
┃분류                │품 목                 │세부품목                                    ┃
┠──────────┼───────────┼──────────────────────┨
┃ 1. 전선 및 전원코  │전선, 케이블 및       │ ① 절연전선(공칭단면적이 95mm2 이하인      ┃
┃드                  │ 코드류               │것에 한정한다)                              ┃
┃                    │                      │ ② 삭제<2023. 3. 20.>                      ┃
┃                    │                      │ ? 코드세트                                 ┃
┃                    ├───────────┴──────────────────────┨
┃                    │비고: 교류전압을 사용하는 제품에 한정하며, 통신 및 데이터 전송을    ┃
┃                    │목적으로만 사용하는 것은 제외한다.                                  ┃
┠──────────┴───────────┴──────────────────────┨
┃비고: 1차 전지(건전지) 및 2차 전지(충전지)만을 전원으로 사용하는 구조의 것은 제외한다.     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""


def _item(label: str | None, name: str, source_text: str, **fields) -> AnnexItem:
    return AnnexItem.model_validate({
        "category_path": ["1. 전선 및 전원코드", "전선, 케이블 및 코드류"],
        "item_label": label,
        "item_name": name,
        "conditions": ["교류전압을 사용하는 제품에 한정하며"],
        "exclusions": ["통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다."],
        "inclusions": [],
        "attributes": [],
        "source_text": source_text,
        **fields,
    })


def _output(**fields) -> AnnexParseOutput:
    values = {
        "scheme": "분류",
        "items": [
            _item("①", "절연전선", "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)"),
            _item("?", "코드세트", "? 코드세트"),
        ],
        "skipped": [AnnexSkippedRow(item_label="②", reason="삭제<2023. 3. 20.>")],
        "notes": ["1차 전지(건전지) 및 2차 전지(충전지)만을 전원으로 사용하는 구조의 것은 제외한다."],
    }
    return AnnexParseOutput.model_validate({**values, **fields})


def test_테두리_문자와_공백을_지운다():
    assert normalize("┃ ① 절연전선  │\n것에 한정 ━━") == "①절연전선것에한정"


def test_여러_줄로_나뉜_칸의_글자를_이어서_찾는다():
    haystacks = _haystacks(_TABLE)

    assert contains(haystacks, "1. 전선 및 전원코드")
    assert contains(haystacks, "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)")
    assert contains(haystacks, "통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다.")


def test_원문의_깨진_글자는_아무_글자_하나로_본다():
    haystacks = _haystacks("┃ 9.오디오?비디오 │ 가. 비디오카메라 ┃")

    assert contains(haystacks, "9.오디오·비디오")
    assert contains(haystacks, "9.오디오?비디오")


@pytest.mark.parametrize("text", ["전기 주전자 만들기", "교류전압 제품에 한정", ""])
def test_원문에_없거나_빈_문구는_찾지_못한다(text):
    assert not contains(_haystacks(_TABLE), text)


def test_범위_안내와_깨진_특수문자는_번호로_세지_않는다():
    labels = source_labels("│12)~16) : 주방가전│\n│?단말장치│\n│ ? 라우터│\n│1)선박국용│")

    assert labels == {"?": 1, "1)": 1}


def test_원문과_맞는_결과는_통과한다():
    assert check_annex(_TABLE, _output()) == []


def test_바꿔_쓴_문구를_실패_사유로_남긴다():
    output = _output(items=[
        _item("①", "절연전선", "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)",
              conditions=["교류 전압 제품에만 적용"]),
        _item("?", "코드세트", "? 코드세트"),
    ])

    assert check_annex(_TABLE, output) == ["items[0] ① 절연전선: 원문에 없는 문구 '교류 전압 제품에만 적용'"]


def test_빠진_번호와_남는_번호를_실패_사유로_남긴다():
    output = _output(skipped=[AnnexSkippedRow(item_label="③", reason="삭제<2023. 3. 20.>")])

    assert check_annex(_TABLE, output) == ["번호 누락: {'②': 1}", "원문보다 많은 번호: {'③': 1}"]


def test_같은_행이_두_번_나오면_실패_사유로_남긴다():
    first = _item("①", "절연전선", "① 절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)")
    output = _output(items=[first, first, _item("?", "코드세트", "? 코드세트")])

    reasons = check_annex(_TABLE, output)

    assert "items[1] ① 절연전선: 중복 행" in reasons
    assert "원문보다 많은 번호: {'①': 1}" in reasons


def test_같은_줄에_나란히_붙은_같은_번호는_한_번만_센다():
    # 운용요령 별표 3의2: 품목·세부품목 칸에 같은 번호가 나란히 있음
    content = "┃1. 재사용전지 │① 재사용전지모듈 │① 재사용전지모듈 ┃\n┃ │② 재사용전지시스템 │② 재사용전지시스템 ┃"

    assert source_labels(content) == {"①": 1, "②": 1}


_NESTED = """\
┌─┬─┬─┐
│대분류 │중분류 │소분류 │부호 │
├─┼─┼─┤
│가. 정보기기 │1) 컴퓨터류 │① 노트북 │A1 │
│ │ ├─┤
│ │ │② 모니터 │A2 │
├─┼─┼─┤
│나. 오디오 │2) 스피커 │ │B1 │
└─┴─┴─┘"""


def _nested_item(path: list[str], label: str, name: str) -> AnnexItem:
    return AnnexItem(category_path=path, item_label=label, item_name=name, conditions=[], exclusions=[],
                     inclusions=[], attributes=[], source_text=f"{label} {name}")


def test_아래_단계가_있는_번호는_분류로_옮겨도_누락이_아니다():
    output = AnnexParseOutput(scheme="대분류", skipped=[], notes=[], items=[
        _nested_item(["가. 정보기기", "1) 컴퓨터류"], "①", "노트북"),
        _nested_item(["가. 정보기기", "1) 컴퓨터류"], "②", "모니터"),
        _nested_item(["나. 오디오"], "2)", "스피커"),
    ])

    assert check_annex(_NESTED, output) == []


def test_분류의_번호로_원문보다_많은_번호를_가리지는_않는다():
    output = AnnexParseOutput(scheme="대분류", skipped=[], notes=[], items=[
        _nested_item(["가. 정보기기", "1) 컴퓨터류"], "①", "노트북"),
        _nested_item(["가. 정보기기", "1) 컴퓨터류"], "①", "노트북"),
        _nested_item(["나. 오디오"], "2)", "스피커"),
    ])

    assert "번호 누락: {'②': 1}" in check_annex(_NESTED, output)
    assert "원문보다 많은 번호: {'①': 1}" in check_annex(_NESTED, output)


_MATRIX = """\
┌─┬─┬─┬─┐
│품목 │전자파 │무선 │비고 │
│ │인체보호 │ │ │
├─┼─┼─┼─┤
│1) 무선기기 │○ │○ │건물 내에서만 │
│ │ │ │사용하는 │
│ ├─┼─┤무선기기 │
│ │o 대표적인 품목: 무선 랜카드, 무선 공유기 │ │ │
└─┴─┴─┴─┘"""


def _matrix_output(*attributes: AnnexAttribute) -> AnnexParseOutput:
    return AnnexParseOutput(scheme="품목", skipped=[], notes=[], items=[AnnexItem(
        category_path=[], item_label="1)", item_name="무선기기", conditions=[], exclusions=[], inclusions=[],
        attributes=list(attributes), source_text="1) 무선기기",
    )])


def test_추가_칸_값은_항목마다_원문과_대조한다():
    output = _matrix_output(
        AnnexAttribute(name="적용분야", values=["전자파인체보호", "무선"]),
        # 가로선 줄 끝에 붙은 글자까지 같은 열로 이어짐
        AnnexAttribute(name="비고", values=["건물 내에서만 사용하는 무선기기"]),
        AnnexAttribute(name="대표 품목", values=["무선 랜카드", "무선 공유기"]),
    )

    assert check_annex(_MATRIX, output) == []


def test_원문에_없는_추가_칸_값은_실패_사유로_남긴다():
    output = _matrix_output(AnnexAttribute(name="대표 품목", values=["무선 랜카드", "블루투스 이어폰"]))

    assert check_annex(_MATRIX, output) == ["items[0] 1) 무선기기: 원문에 없는 대표 품목 값 '블루투스 이어폰'"]


def test_표시_기호만_있는_추가_칸_값은_실패_사유로_남긴다():
    # 행렬 열 이름을 name으로, ○를 값으로 쓴 경우
    output = _matrix_output(AnnexAttribute(name="무선", values=["○"]))

    assert check_annex(_MATRIX, output) == ["items[0] 1) 무선기기: 무선 값이 표시 기호뿐 '○'"]


def test_원문에서_깨진_번호는_원본_파일에서_읽은_원문자_번호와_짝짓는다():
    # API 별표내용은 ⑯·➄ 등을 ?로 깨뜨림. 원본 파일에서 읽으면 제대로 나옴
    content = "┃1. 전기기기 │⑮ 빙삭기 ┃\n┃ │? 전기고기갈개 ┃\n┃ │? 저속전동이륜차 ┃"
    output = AnnexParseOutput(scheme="전기기기", skipped=[], notes=[], items=[
        _nested_item(["1. 전기기기"], "⑮", "빙삭기"),
        _nested_item(["1. 전기기기"], "⑯", "전기고기갈개"),
        _nested_item(["1. 전기기기"], "➄", "저속전동이륜차"),
    ])

    assert check_annex(content, output) == []
