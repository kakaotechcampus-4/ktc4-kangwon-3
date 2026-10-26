"""전파 근거 조회·대상기자재 파싱을 실제 법제처 응답 픽스처로 검증한다. 실제 API는 호출하지 않는다."""

import pytest

from app.tools.common.law import EvidenceUnavailable, LawLookupError
from app.tools.radio.evidence import load_radio_evidence, parse_bands

from .conftest import AS_OF, NEXT_NOTICE_SERIAL, NOTICE_SERIAL


def _item(evidence, item_id):
    return next(item for item in evidence.items if item.item_id == item_id)


def test_무선설비_1_10절만_읽고_행마다_평가유형이_하나씩_있다(radio_evidence):
    sections = {item.section.split(".")[0] for item in radio_evidence.items}
    assert sections == {str(number) for number in range(1, 11)}
    assert len(radio_evidence.items) == 230
    assert all(len(item.assessment) == 1 for item in radio_evidence.items)
    codes = [item.code for item in radio_evidence.items]
    assert all(codes) and len(codes) == len(set(codes))


def test_평가유형과_적용분야는_오른쪽부터_센_표시_칸으로_정한다(radio_evidence):
    data = _item(radio_evidence, "LARN8")
    assert data.path == ("라.특정소출력무선기기", "8) 무선데이터통신시스템용무선기기")
    assert data.assessment == ("적합인증",)
    assert data.applied_fields == ("전자파적합성", "무선", "전자파흡수율")
    assert _item(radio_evidence, "LARN4").assessment == ("적합등록",)
    assert _item(radio_evidence, "LOW21").assessment == ("자기적합확인",)


def test_여러_행에_걸친_바깥_분류명과_줄바꿈된_이름을_잇는다(radio_evidence):
    wlan = _item(radio_evidence, "LARN5")
    assert wlan.path[:2] == ("라.특정소출력무선기기", "5)무선랜을포함한무선접속시스템용무선기기")
    assert wlan.bands == ((5150.0, 5350.0), (5470.0, 5850.0))
    assert _item(radio_evidence, "DCP24").path[0] == "사.코드없는전화기"
    assert _item(radio_evidence, "LARN5D").remark == "지하철 내에서만 사용하는 무선기기"
    assert wlan.name == "무선랜을포함한무선접속시스템용무선기기 > 5150∼5350㎒,5470∼5850㎒주파수 대역"
    assert _item(radio_evidence, "CB").name == "생활무선국용 무선설비의 기기"


def test_삭제된_행은_뺀다(radio_evidence):
    assert not any("삭제" in "".join(item.path).replace(" ", "") for item in radio_evidence.items)


def test_절별_비고를_따로_모은다(radio_evidence):
    notes = radio_evidence.section_notes["5. 신고하지 아니하고 개설할 수 있는 무선국용 무선설비의 기기"]
    assert "전자파흡수율" in notes and "20cm" in notes


def test_시행령_별표_6의2에서_개인_사용_1대_면제를_찾는다(radio_evidence):
    personal = radio_evidence.personal_use
    assert personal.label == "자"
    assert personal.quantity == "1대"
    assert "반입일부터 1년 이내에 판매하는 경우는 제외한다" in personal.target
    assert "자기적합확인" in personal.content


def test_전파법_제58조의2_항별_원문을_꺼낸다(radio_evidence):
    assert radio_evidence.obligation["①"].startswith("① 방송통신기자재와")
    assert "적합인증을 받아야 한다" in radio_evidence.obligation["②"]
    assert "적합등록" in radio_evidence.obligation["③"]
    assert "자기적합확인" in radio_evidence.obligation["④"]


def test_기준일에_시행_중인_고시를_고르고_시행_예정본은_쓰지_않는다(fake_law):
    evidence = load_radio_evidence(fake_law, AS_OF)
    assert evidence.notice.version_id == NOTICE_SERIAL
    assert ("get_admrul_text", NEXT_NOTICE_SERIAL) not in fake_law.calls


def test_면제_목을_찾지_못하면_근거를_쓰지_않는다(fake_law):
    body = fake_law.law_bodies["278235"]
    annex = body.annexes[0].model_copy(update={"annex_content": "1. 법 제58조의3제1항제1호에 따른 적합성평가 면제대상 기자재"})
    fake_law.law_bodies["278235"] = body.model_copy(update={"annexes": [annex]})
    with pytest.raises(EvidenceUnavailable):
        load_radio_evidence(fake_law, AS_OF)


def test_법제처_응답_오류는_전용_예외로_바꾼다(fake_law):
    fake_law.error = RuntimeError("법제처 API 오류: OC=secret")
    with pytest.raises(LawLookupError) as caught:
        load_radio_evidence(fake_law, AS_OF)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("text,expected", [
    ("2.4GHz", [(2400.0, 2400.0)]),
    ("5150∼5350㎒, 5470∼5850㎒", [(5150.0, 5350.0), (5470.0, 5850.0)]),
    ("2400-2483.5MHz", [(2400.0, 2483.5)]),
    ("13.56㎒", [(13.56, 13.56)]),
    ("125kHz", [(0.125, 0.125)]),
    ("블루투스 5.3", []),
])
def test_주파수_표기를_MHz로_읽는다(text, expected):
    assert parse_bands(text) == expected
