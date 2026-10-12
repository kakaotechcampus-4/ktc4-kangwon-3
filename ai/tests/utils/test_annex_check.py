"""별표 파싱 결과의 원문 대조(문구·번호)를 실제 별표 원문으로 확인한다."""

from pathlib import Path

import pytest

from app.schemas.agents.annex import AnnexItem, AnnexParseOutput, AnnexSkippedRow
from app.utils.annex_check import _haystacks, check_annex, contains, normalize, source_labels

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "annex"
_NOTICE_1 = _FIXTURES / "전기용품및생활용품안전관리운용요령_별표0001-00" / "content.txt"
_NOTICE_3 = _FIXTURES / "전기용품및생활용품안전관리운용요령_별표0003-00" / "content.txt"
_RADIO_1 = _FIXTURES / "방송통신기자재등의적합성평가에관한고시_별표0001-00" / "content.txt"

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
    haystacks = _haystacks(_NOTICE_1.read_text(encoding="utf-8"))

    assert contains(haystacks, "1. 전선 및 전원코드")
    assert contains(haystacks, "④ 코드세트(반도체장비 전용의 것으로 전선 또는 케이블 양 끝단에 "
                               "기기간 상호연결을 위한 커넥터가 부착된 것은 제외한다)")
    assert contains(haystacks, "교류전원 30V 이하, 직류 전원 42V 이하에서 사용하는 것을 포함한다.")


def test_원문의_깨진_글자는_아무_글자_하나로_본다():
    haystacks = _haystacks(_NOTICE_3.read_text(encoding="utf-8"))

    assert contains(haystacks, "9.오디오·비디오")
    assert contains(haystacks, "9.오디오?비디오")


@pytest.mark.parametrize("text", ["전기 주전자 만들기", "교류전압 제품에 한정", ""])
def test_원문에_없거나_빈_문구는_찾지_못한다(text):
    assert not contains(_haystacks(_NOTICE_1.read_text(encoding="utf-8")), text)


def test_운용요령_별표1의_번호는_세부품목과_삭제_행을_합친_수다():
    # 코드 파서(#290 parse_annex) 기준 세부품목 131개 + 삭제 행 ④·⑫·② 3개
    assert sum(source_labels(_NOTICE_1.read_text(encoding="utf-8")).values()) == 134


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


def test_전파_고시_별표1은_범위_안내를_빼고_번호를_센다():
    labels = source_labels(_RADIO_1.read_text(encoding="utf-8"))

    assert sum(labels.values()) == 311
    assert "?" not in labels


def test_같은_줄에_나란히_붙은_같은_번호는_한_번만_센다():
    # 운용요령 별표 3의2: 품목·세부품목 칸에 같은 번호가 나란히 있음
    content = (_FIXTURES / "전기용품및생활용품안전관리운용요령_별표0003-02" / "content.txt").read_text(encoding="utf-8")

    assert source_labels(content) == {"①": 1, "②": 1}
