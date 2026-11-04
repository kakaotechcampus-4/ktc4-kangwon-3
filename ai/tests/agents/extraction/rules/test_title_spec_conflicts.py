"""제목·옵션명과 스펙표가 같은 항목을 다르게 적은 모순을 코드 규칙으로 잡는다.

초안 50건 측정(2026-11-05)에서 모델(gpt-4.1-mini)은 제목↔스펙표 모순 12건을 프롬프트를 두 번 보강해도
보고하지 않았다. 스펙표가 맞겠거니 하고 제목을 넘기기 때문이다. 자주 나온 유형(사용 대상 성별, 연령 범위,
단위 붙은 수치, 재질, 전원 방식, 계절)을 규칙으로 잡고, 모순 문장에는 양쪽 표기를 원문 그대로 넣는다.
"""

from app.agents.extraction.title_spec_conflicts import detect_title_spec_conflicts

# 스펙표는 "키" 줄 다음에 "값" 줄이 오거나(알리·테무), "키: 값" 한 줄이다(테무 옵션).


def _spec(*pairs: tuple[str, str]) -> str:
    return "\n".join(f"{key}\n{value}" for key, value in pairs)


def test_제목은_남성용인데_스펙표_대상이_남녀공용이면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["kasili 2pcs 남성용 강모 칫솔"], [_spec(("대상 고객", "남녀공용-성인"))]
    )

    assert len(conflicts) == 1
    assert "남성용" in conflicts[0] and "남녀공용" in conflicts[0]


def test_제목과_스펙표_대상이_같으면_모순이_아니다():
    assert detect_title_spec_conflicts(["남성용 압박 무릎 지지대"], [_spec(("적용 대상", "남성"))]) == []


def test_제목_연령_범위와_스펙표_연령대가_다르면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["여아용 면 메쉬 아기 양말, 0-2 세 영아용"], [_spec(("연령대", "1~3세"), ("성별", "남녀공용"))]
    )

    assert any("0-2 세" in c and "1~3세" in c for c in conflicts)


def test_연령_단위가_세와_년으로_다르게_적혀도_같은_범위면_모순이_아니다():
    assert detect_title_spec_conflicts(["다트 장난감 발사기, 3세 이상"], [_spec(("사용연령", "3년 이상"))]) == []


def test_제목_연령은_하한만_있고_스펙표에_상한이_있으면_모순이_아니다():
    assert detect_title_spec_conflicts(["Wooden Play Kitchen Ages 3+"], [_spec(("Recommend Age", "3-6Y"))]) == []


def test_제목_용량과_스펙표_용량이_단위는_같은데_값이_다르면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["대형 635L 스테인리스 스틸 양문형 냉장고"], [_spec(("용량", "60L 미만"), ("냉동실 용량", "60L 미만"))]
    )

    assert len(conflicts) == 1
    assert "635L" in conflicts[0] and "60L" in conflicts[0]


def test_제목에_여러_용량을_나열했는데_하나라도_스펙표와_맞으면_모순이_아니다():
    assert detect_title_spec_conflicts(
        ["휴대용 보조 배터리 10000/20000mAh PD 22.5W"], [_spec(("배터리 용량", "10000mAh"), ("출력", "22.5W"))]
    ) == []


def test_제목_안에_한_자리만_다른_같은_단위_수치가_둘이면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["KOSHARE 1.5V AA 4255mWh 리튬이온 배터리 4225mWh 4개입"], [_spec(("유형", "충전식 배터리"))]
    )

    assert len(conflicts) == 1
    assert "4255mWh" in conflicts[0] and "4225mWh" in conflicts[0]


def test_제목_재질이_스펙표_소재_줄에_없으면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["스트랩이 있는 검은색 구리 합금 무릎 보호대"], [_spec(("성분", "90% 나일론, 10% 폴리에스테르"))]
    )

    assert len(conflicts) == 1
    assert "구리" in conflicts[0] and "나일론" in conflicts[0]


def test_제목_재질이_스펙표에_영문_동의어로_있으면_모순이_아니다():
    assert detect_title_spec_conflicts(["여아용 면 메쉬 아기 양말"], [_spec(("소재 구성", "72% Cotton 25% Polyester"))]) == []


def test_스펙표에_소재_줄이_없으면_재질_모순을_만들지_않는다():
    assert detect_title_spec_conflicts(["재사용 가능한 실리콘 빨대 6개"], [_spec(("색상", "Mix colors"))]) == []


def test_스펙표가_전자식_아니요인데_교류_전원을_적으면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["초음파 40KHz 캐비테이션 바디 마사지기"],
        [_spec(("전자식", "아니요"), ("전원 공급", "교류"), ("전압", "<50V 교류"))],
    )

    assert len(conflicts) == 1
    assert "전자식" in conflicts[0] and "교류" in conflicts[0]


def test_전자식_아니요에_전원_없음이면_모순이_아니다():
    assert detect_title_spec_conflicts(
        ["발 지압 매트 비전동"], [_spec(("전자식", "아니요"), ("전원 공급", "전기 없음"))]
    ) == []


def test_제목은_충전식인데_스펙표_전원이_전기_없음이면_모순이다():
    conflicts = detect_title_spec_conflicts(["USB 충전식 손난로"], [_spec(("전원 공급", "전기 없음"))])

    assert len(conflicts) == 1
    assert "충전식" in conflicts[0] and "전기 없음" in conflicts[0]


def test_제목_계절과_스펙표_계절이_다르면_모순이다():
    conflicts = detect_title_spec_conflicts(
        ["2025 신상 봄/여름용 플로럴 레이스 세트"], [_spec(("계절:", "봄/가을"))]
    )

    assert len(conflicts) == 1
    assert "봄/여름" in conflicts[0] and "봄/가을" in conflicts[0]


def test_제목_없이_스펙표만_있으면_제목_규칙은_돌지_않는다():
    assert detect_title_spec_conflicts([], [_spec(("계절", "봄/가을"), ("성별", "남녀공용"))]) == []


def test_모순_문장은_양쪽_표기를_원문_그대로_담는다():
    [conflict] = detect_title_spec_conflicts(["남성용 칫솔"], [_spec(("성별", "남녀공용-성인"))])

    assert conflict == '제목은 "남성용"인데 스펙표 성별은 "남녀공용-성인"입니다. 판매자 표기가 서로 달라 확인이 필요합니다.'
