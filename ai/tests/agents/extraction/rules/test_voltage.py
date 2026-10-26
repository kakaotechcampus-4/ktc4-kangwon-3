"""rules.py 전압 표기 추출: 한정어·공차·범위 표기 (#90, 전안법 직류 30V 초과 기준 판정 보호)."""

from app.agents.extraction.rules import extract_rule_based_attributes


def _voltages(text_blocks: list[str]) -> list[str]:
    return [a.value for a in extract_rule_based_attributes(text_blocks) if a.name == "전압 표기"]


def test_전압_한정어가_값에_함께_보존된다():
    # "36V 이하"는 정격이 36V라는 뜻이 아니라 상한이 36V라는 뜻이다. 한정어를 떼고
    # "36V"로 넘기면 하위 판정(전안법의 직류 30V 초과 기준)이 틀어진다.
    text_blocks = ["저전압(36V 이하) 어린이용", "작동 전압 ≤36V", "최대 12V 출력", "입력 5V 이상"]

    assert _voltages(text_blocks) == ["36V 이하", "≤36V", "최대 12V", "5V 이상"]


def test_하한_한정어도_상한과_똑같이_보존된다():
    # 상한만 처리하면 "최소 5V"가 "5V"로 둔갑해서, 실제로는 220V인 제품이
    # 저전압으로 넘어간다. 상한·하한을 대칭으로 다뤄야 한다.
    text_blocks = ["≥36V", ">36V", "최소 5V", "12V 이내", "12V max"]

    assert _voltages(text_blocks) == ["≥36V", ">36V", "최소 5V", "12V 이내", "12V max"]


def test_공차_표기는_전압으로_잡지_않는다():
    # "DC 5V±0.5V"에서 0.5V는 정격이 아니라 공차다. 앞자리를 건너뛴 "5V"가 새로
    # 생기지도 않아야 한다(원문에 없던 전압을 만들어내면 안 된다).
    assert _voltages(["DC 5V±0.5V", "5V +0.2V"]) == ["5V", "5V"]


def test_한정어가_없는_전압은_그대로_뽑는다():
    assert _voltages(["정격전압 220V", "220V정격", "AC-220V-A1 모델"]) == ["220V", "220V", "220V"]


def test_범위_표기는_양쪽_값으로_쪼개진다():
    # 정규식은 범위를 하나의 개념으로 이해하지 못한다. "3.7V~4.2V"는 두 항목이 되며,
    # 뒤쪽은 "~4.2V"로 남아 상한이라는 것만 전달된다. 범위 해석은 LLM 몫이다.
    assert _voltages(["DC 3.7V~4.2V 충전"]) == ["3.7V", "~4.2V"]


def test_앞_숫자에_단위가_없는_범위는_원문_그대로_한_값으로_담는다():
    # 뒤 숫자만 잡으면 "110-240V"가 "240V" 단일 전압처럼 넘어간다(#399 리뷰).
    assert _voltages(["Rated Voltage: 110-240V", "AC100-240V", "공칭 전압 0~5V", "210-240V용"]) == [
        "110-240V", "100-240V", "0~5V", "210-240V"]


def test_네_자리_이상_숫자_뒤의_전압은_범위로_묶지_않는다():
    # 전지 규격(18650)·연도 뒤에 하이픈으로 붙은 전압은 범위가 아니다.
    assert _voltages(["18650-3.7V 배터리", "2023-12V"]) == ["3.7V", "12V"]


def test_입력_출력_작동_전압도_정격전압이라고_부르지_않는다():
    # 정규식은 칸 이름을 모른다. 출력 전압을 "정격전압"이라고 부르면 원문에 없는 '정격'을 만든다
    # (전압이 적힌 줄 25개 중 제품 정격 전압 줄은 2개, #369). 칸 이름은 source_text에 남긴다.
    text_blocks = ["USB 출력 전압: 5V/DC", "어댑터 출력 전압: 8.5V/DC", "Input: 5V/2A", "작동 전압 ≤36V"]

    attributes = extract_rule_based_attributes(text_blocks)

    assert {a.name for a in attributes} == {"전압 표기"}
    assert [a.value for a in attributes] == ["5V", "8.5V", "5V", "≤36V"]
    assert "USB 출력 전압" in attributes[0].source_text
