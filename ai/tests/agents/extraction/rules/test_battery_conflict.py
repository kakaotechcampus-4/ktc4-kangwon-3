"""rules.py 배터리 용량 모순 후보: 용량 표기와 '배터리 미포함'이 함께 있으면 검토 후보로 보고 (#40)."""

from app.agents.extraction.rules import detect_battery_capacity_conflict


def test_용량_표기와_배터리_미포함_문구가_같이_있으면_모순_후보로_잡는다():
    # Given: 실제 테스트 중 발견한 파워뱅크 케이스와 동일한 패턴
    text_blocks = [
        "9482 블랙 블록 아이폰 MagSafe 외장 배터리 케이스 MagSafe 1460mAh 케이스",
        "배터리 속성 배터리 미포함",
    ]

    conflicts = detect_battery_capacity_conflict(text_blocks)

    assert len(conflicts) == 1
    assert "1460mAh" in conflicts[0]
    # 확정이 아니라 검토가 필요한 후보로 전달한다(리뷰 반영).
    assert "모순 가능성" in conflicts[0]


def test_용량_표기만_있고_미포함_문구가_없으면_모순이_아니다():
    assert detect_battery_capacity_conflict(["보조배터리 10000mAh 대용량"]) == []


def test_패턴이_없으면_모순_후보도_없다():
    assert detect_battery_capacity_conflict(["그냥 평범한 설명 문구입니다."]) == []


def test_부속품_배터리_미포함은_모순으로_보지_않는다():
    # 본체 내장 배터리 용량과 별개로 리모컨용 배터리가 미포함인 것은 모순이 아니다.
    text_blocks = ["드론 내장 배터리 1500mAh", "리모컨용 AA 배터리 미포함"]

    assert detect_battery_capacity_conflict(text_blocks) == []


def test_부속품_문구가_있어도_본체_배터리_미포함이_따로_있으면_모순_후보다():
    text_blocks = [
        "MagSafe 1460mAh 케이스",
        "리모컨용 AA 배터리 미포함",
        "배터리 속성 배터리 미포함",
    ]

    assert len(detect_battery_capacity_conflict(text_blocks)) == 1
