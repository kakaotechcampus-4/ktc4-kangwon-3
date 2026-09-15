"""채점 규칙 자체를 검증한다. LLM을 부르지 않아 API 키 없이 CI에서 돈다.

채점 기준이 틀리면 그걸로 잰 모든 수치가 무의미해지므로, 평가 코드 중
여기가 가장 먼저 테스트되어야 한다.
"""

import pytest

from app.eval.grading import (
    Grade,
    attribute_names_for,
    grade_attribute_value,
    Stability,
    classify_stability,
    grade_boolean,
    grade_forbidden_items,
    grade_keywords,
    grade_required_items,
    grade_verbatim,
    is_hard_flip,
)


# --- 3-state boolean: 9가지 조합 전부 ---------------------------------------


@pytest.mark.parametrize(
    "truth, predicted, expected",
    [
        (True, True, Grade.OK),
        (False, False, Grade.OK),
        (None, None, Grade.OK),
        # 있는 것을 "없음 확인"으로 확정 -> 툴이 안 돌아 규제를 놓친다
        (True, False, Grade.C1),
        # 근거가 없는데 확정 -> 하위 단계가 그 확정을 신뢰한다
        (None, True, Grade.C1),
        (None, False, Grade.C1),
        # null로 넘기면 하위에서 "확인 필요"로 처리할 수 있다
        (True, None, Grade.C2),
        (False, None, Grade.C2),
        # 없는데 있다고 봄 -> 불필요한 툴 실행. 판단은 안 틀린다
        (False, True, Grade.C3),
    ],
)
def test_boolean_채점표가_9가지_조합을_모두_구분한다(truth, predicted, expected):
    assert grade_boolean(truth, predicted) is expected


def test_없는_것을_없다고_확정한_것과_모른다고_한_것은_등급이_다르다():
    # 같은 "정답 아님"이어도 false는 적극적 주장, null은 유보라 위험이 다르다.
    assert grade_boolean(True, False) is Grade.C1
    assert grade_boolean(True, None) is Grade.C2


def test_boolean에_올_수_없는_값은_거부한다():
    with pytest.raises(ValueError):
        grade_boolean(True, "yes")


# --- 원문 보존 필드(target_age) ---------------------------------------------


def test_원문이_그대로_들어_있으면_정답이다():
    assert grade_verbatim("만 14세 이상", "만 14세 이상") is Grade.OK
    assert grade_verbatim("만 14세 이상", "권장연령: 만 14세 이상입니다") is Grade.OK


def test_원문을_줄여_쓰면_오답이다():
    # "만 14세 이상"을 "14세"로 줄이면 어린이제품 판정 근거가 사라진다.
    assert grade_verbatim("만 14세 이상", "14세") is Grade.C1


def test_연령_표기가_없는데_지어내면_치명이고_비우면_정답이다():
    assert grade_verbatim(None, "3세 이상") is Grade.C1
    assert grade_verbatim(None, None) is Grade.OK


def test_연령_표기가_있는데_비우면_미탐이다():
    assert grade_verbatim("만 14세 이상", None) is Grade.C2


# --- 표현이 흔들려도 되는 텍스트 필드 ---------------------------------------


def test_필수_키워드가_모두_있으면_정답이다():
    assert grade_keywords(["드론"], None, "4채널 무선조종 드론") is Grade.OK
    assert grade_keywords(["드론", "무선"], None, "4채널 무선조종 드론") is Grade.OK


def test_필수_키워드가_하나라도_빠지면_오답이다():
    assert grade_keywords(["드론", "카메라"], None, "4채널 무선조종 드론") is Grade.C1


def test_허용_목록_중_하나면_정답이다():
    # "방향제"와 "디퓨저"처럼 같은 뜻의 표기를 미리 등록해둔다.
    assert grade_keywords(None, ["방향제", "디퓨저"], "디퓨저") is Grade.OK
    assert grade_keywords(None, ["방향제", "디퓨저"], "선풍기") is Grade.C1


def test_채점_기준이_없으면_통과시킨다():
    # 정답표에 기준을 안 적은 필드까지 오답으로 세면 수치가 왜곡된다.
    assert grade_keywords(None, None, "아무 값") is Grade.OK
    assert grade_keywords([], [], None) is Grade.OK


# --- 리스트 필드 -------------------------------------------------------------


def test_요구한_항목을_놓치면_미탐으로_센다():
    required = [{"name": "배터리 용량", "value": "1460mAh"}]
    present = [{"name": "배터리 용량", "value": "1460mAh"}]
    assert grade_required_items(required, present) == [Grade.OK]
    assert grade_required_items(required, []) == [Grade.C2]


def test_페이지에_없는_값을_지어내면_치명으로_센다():
    forbidden = [{"name": "정격전압", "value": "220V"}]
    assert grade_forbidden_items(forbidden, []) == [Grade.OK]
    assert grade_forbidden_items(forbidden, [{"name": "정격전압", "value": "220V"}]) == [Grade.C1]


# --- 반복 실행 안정성 ---------------------------------------------------------


def test_N회_모두_정답이면_안정_정답이다():
    grades = [Grade.OK, Grade.OK, Grade.OK]
    assert classify_stability(grades, [True, True, True]) is Stability.STABLE_OK


def test_N회_모두_같은_오답이면_안정_오답이다():
    # 체계적 오류. 몇 번을 돌려도 같은 답이라 정답표 없이는 발견되지 않는다.
    grades = [Grade.C1, Grade.C1, Grade.C1]
    assert classify_stability(grades, [False, False, False]) is Stability.STABLE_WRONG


def test_값이_갈리면_등급이_같아도_불안정이다():
    # 정답이 None일 때 True도 False도 C1이라, 등급만 보면 "안정적으로 틀린다"로
    # 잘못 읽힌다. 실제로는 근거가 없어서 흔들리는 것이다.
    grades = [Grade.C1, Grade.C1, Grade.C1]
    assert classify_stability(grades, [True, False, True]) is Stability.UNSTABLE


def test_실행_결과가_없으면_분류할_수_없다():
    with pytest.raises(ValueError):
        classify_stability([], [])


def test_확정끼리_진동한_경우만_심각한_진동으로_본다():
    # True <-> False는 정반대 확정을 번갈아 주장하는 것이라 더 심각하다.
    assert is_hard_flip([True, False, True]) is True
    # 확정 <-> null은 "확신이 없다"는 신호라도 남는다.
    assert is_hard_flip([True, None, None]) is False
    assert is_hard_flip([False, None, False]) is False
    assert is_hard_flip([True, True, True]) is False


# --- attributes 값 기준 채점 (실측으로 드러난 문제) --------------------------


def test_한_항목에_여러_값을_이어_써도_각각_찾는다():
    # 실측: 모델이 "CE-RoHS; CE-EMC(Electric)"를 한 항목에 담았다.
    # 정확 일치를 요구하면 사실을 포착했는데도 "놓쳤다"로 잘못 센다.
    attrs = [{"name": "인증정보", "value": "CE-RoHS; CE-EMC(Electric)"}]

    assert grade_attribute_value("CE-RoHS", attrs) is Grade.OK
    assert grade_attribute_value("CE-EMC", attrs) is Grade.OK
    assert grade_attribute_value("KC", attrs) is Grade.C2


def test_항목_이름이_달라도_값이_같으면_찾는다():
    # 실측: 같은 용량을 런에 따라 "용량"/"배터리 용량"으로 적었다.
    assert grade_attribute_value("1460mAh", [{"name": "용량", "value": "1460mAh"}]) is Grade.OK
    assert grade_attribute_value("1460mAh", [{"name": "배터리 용량", "value": "1460mAh"}]) is Grade.OK


def test_값을_담은_항목_이름을_모아_이름_흔들림을_볼_수_있다():
    assert attribute_names_for("1460mAh", [{"name": "용량", "value": "1460mAh"}]) == ["용량"]
    assert attribute_names_for("없는값", [{"name": "용량", "value": "1460mAh"}]) == []


def test_값_토큰은_대소문자를_구분하지_않는다():
    # 같은 페이지에 "1460mAh"와 "1460mah"가 섞여 있는 경우가 있다.
    assert grade_attribute_value("1460mAh", [{"name": "용량", "value": "1460mah"}]) is Grade.OK
