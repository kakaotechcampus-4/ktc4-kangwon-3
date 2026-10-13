"""별표 칸 글자를 한정·제외·포함 문구, 예시 품목, 규제 구분으로 나누는 규칙을 확인한다."""

import pytest

from app.utils.annex_file.text import (EXAMPLE_ATTRIBUTE, classify_phrases, find_title, join_lines, note_entries,
                                       scheme_from_title, split_examples, split_qualifier)


def test_칸_안_여러_줄을_잇고_병합_칸에_되풀이된_줄은_한_번만_둔다():
    assert join_lines("7. 전기기기\n7. 전기기기\n7. 전기기기") == "7. 전기기기"
    assert join_lines("전선, 케이블 및\n코드류") == "전선, 케이블 및 코드류"
    assert join_lines("10. 정보․통신․\n사무기기") == "10. 정보․통신․사무기기"


def test_비고를_번호_항목마다_나누고_항목_안_줄바꿈은_잇는다():
    text = "비고:\n1. 차량 등에 설치된 것은 제외한다.\n2. 교류전원 30V 이하에서 사용\n하는 것을 포함한다."

    assert note_entries(text) == ["차량 등에 설치된 것은 제외한다.", "교류전원 30V 이하에서 사용 하는 것을 포함한다."]


def test_한_문장에_이어진_한정과_제외를_경계에서_나눈다():
    text = "비고: 교류전압을 사용하는 제품에 한정하며, 통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다."

    assert classify_phrases(text) == (
        ["교류전압을 사용하는 제품에 한정하며"],
        ["통신 및 데이터 전송을 목적으로만 사용하는 것은 제외한다."],
        [],
    )


def test_포함_문구와_그_밖의_문장을_나눈다():
    text = "비고: 직류전원 42 V 이하에서 사용하는 것을 포함하며, 이 경우 공급자적합성확인대상으로 한다."

    assert classify_phrases(text) == (["이 경우 공급자적합성확인대상으로 한다."], [],
                                      ["직류전원 42 V 이하에서 사용하는 것을 포함하며"])


def test_이름_끝_괄호의_한정_문구를_떼어_낸다():
    assert split_qualifier("절연전선(공칭단면적이 95mm2 이하인 것에 한정한다)") == (
        "절연전선", ["공칭단면적이 95mm2 이하인 것에 한정한다"], [], [])
    assert split_qualifier("가. 텐트(난방용 텐트를 포함한다)") == ("가. 텐트", [], [], ["난방용 텐트를 포함한다"])


@pytest.mark.parametrize("name", ["가(假) 속눈썹(인조 속눈썹)", "수영보조용품(착용형)", "코드세트"])
def test_한정_제외_포함이_아닌_괄호는_이름에_둔다(name):
    assert split_qualifier(name) == (name, [], [], [])


def test_신설_표시는_이름에서_뺀다():
    assert split_qualifier("호. 전기청소기 (신  설)")[0] == "호. 전기청소기"


def test_이름_끝_괄호의_품목_나열은_예시_품목으로_옮긴다():
    name, attributes = split_examples("투영기(슬라이드 투영기, OHP, 필름 투영기 등)")

    assert name == "투영기"
    assert [(attribute.name, attribute.values) for attribute in attributes] == [
        (EXAMPLE_ATTRIBUTE, ["슬라이드 투영기", "OHP", "필름 투영기"])]


@pytest.mark.parametrize("name", [
    "전동형 롤스크린(전동식 커튼, 셔터, 그릴, 차양, 블라인드 및 전기구동장치를 말한다)",
    "디지털TV(스마트 TV, IPTV 등을 말한다)",
])
def test_문장으로_끝나거나_항목이_적은_괄호는_나누지_않는다(name):
    assert split_examples(name) == (name, [])


def test_제목에서_규제_구분을_뗀다():
    assert scheme_from_title("안전인증대상전기용품 세부품목(제3조 관련)") == "안전인증대상전기용품"
    assert scheme_from_title("공급자적합성확인대상 전기용품의 세부품목(제3조 관련)") == "공급자적합성확인대상 전기용품"


def test_별표_머리가_아닌_마지막_문단을_제목으로_본다():
    assert find_title(["[별표 4]", "안전인증대상생활용품 세부품목(제3조 관련)"]) == "안전인증대상생활용품 세부품목(제3조 관련)"
    assert find_title(["■ 전파법 시행령 [별표 6의2] <개정 2025. 4. 1.>"]) is None


@pytest.mark.parametrize("text", ["비고) 방폭형인 것은 제외한다.", "비고) 비고) 방폭형인 것은 제외한다.", "비고 : 방폭형인 것은 제외한다."])
def test_여러_모양의_비고_머리를_뺀다(text):
    assert note_entries(text) == ["방폭형인 것은 제외한다."]


def test_머리만_있는_비고_줄은_항목으로_두지_않는다():
    assert note_entries("비고\n1. 재사용전지를 포함한다.") == ["재사용전지를 포함한다."]


def test_적용_안전기준_표_제목에서_규제_구분을_뗀다():
    assert scheme_from_title("안전인증대상어린이제품의 종류 및 적용 안전기준(제2조제1항 관련)") == "안전인증대상어린이제품"


def test_번호_뒤_공백이_없어도_번호를_떼고_소수는_둔다():
    assert note_entries("비고:\n1.「전파법」에 따른다.\n2. 정격입력 1.5kW 이하") == ["「전파법」에 따른다.", "정격입력 1.5kW 이하"]
    assert note_entries("비고: 1.5kW 이하인 것만 해당된다.") == ["1.5kW 이하인 것만 해당된다."]
