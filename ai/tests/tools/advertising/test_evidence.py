"""표시·광고 근거 조문을 기준일 판 본문에서 읽는지 확인한다. 본문은 실제 법제처 응답 픽스처."""

from datetime import date

import pytest

from app.schemas.advertising import AdvertisingRiskType as RiskType
from app.tools.advertising.evidence import (
    DESIGNATION_NOTICE, LAW_ACT, SUBSTANTIATION_NOTICE, AdvertisingEvidence, load_advertising_evidence,
)
from app.tools.common.law import EvidenceUnavailable

from .conftest import FakeLaw

AS_OF = date(2026, 11, 7)
DESIGNATION_PERFORMANCE = ("라. 표시ㆍ광고된 상품의 성능이나 효능이 객관적으로 확인될 수 없거나 확인되지 아니하였는데도 불구하고 "
                           "확실하게 발휘되는 것처럼 표시ㆍ광고하는 행위")


def _pick(evidence: AdvertisingEvidence, key: str):
    return {
        "article_3": evidence.article_3,
        "article_5": evidence.article_5,
        "medicinal": evidence.medicinal_effect,
        "target_body": evidence.substantiation_targets[RiskType.BODY_EFFECT],
        "target_safety": evidence.substantiation_targets[RiskType.SAFETY_CERTIFICATION],
        "target_performance": evidence.substantiation_targets[RiskType.PERFORMANCE_QUALITY],
        "target_ranking": evidence.substantiation_targets[RiskType.RANKING_ABSOLUTE],
        "type_body": evidence.type_sources[RiskType.BODY_EFFECT],
        "type_safety": evidence.type_sources[RiskType.SAFETY_CERTIFICATION],
        "type_performance": evidence.type_sources[RiskType.PERFORMANCE_QUALITY],
        "type_ranking": evidence.type_sources[RiskType.RANKING_ABSOLUTE],
    }[key]


# 코드에 고정해 쓰던 인용과 대조함. 제3조만 각 호까지 포함돼 고정 인용보다 김
@pytest.mark.parametrize("key, law_name, article, quoted", [
    ("article_3", LAW_ACT[0], "제3조 제1항",
     "① 사업자등은 소비자를 속이거나 소비자로 하여금 잘못 알게 할 우려가 있는 표시ㆍ광고 행위로서 공정한 거래질서를 "
     "해칠 우려가 있는 다음 각 호의 행위를 하거나 다른 사업자등으로 하여금 하게 하여서는 아니 된다. "
     "1. 거짓ㆍ과장의 표시ㆍ광고 2. 기만적인 표시ㆍ광고 3. 부당하게 비교하는 표시ㆍ광고 4. 비방적인 표시ㆍ광고"),
    ("article_5", LAW_ACT[0], "제5조 제1항",
     "① 사업자등은 자기가 한 표시ㆍ광고 중 사실과 관련한 사항에 대하여는 실증(實證)할 수 있어야 한다."),
    ("target_body", SUBSTANTIATION_NOTICE[0], "Ⅲ 1", "1. 인체에 직접적으로 영향을 미친다는 내용"),
    ("target_safety", SUBSTANTIATION_NOTICE[0], "Ⅲ 2", "2. 안전 또는 환경, 신기술과 관련된 내용인 경우"),
    ("target_performance", SUBSTANTIATION_NOTICE[0], "Ⅲ 3", "3. 성능, 효능, 품질에 관한 내용인 경우"),
    ("target_ranking", SUBSTANTIATION_NOTICE[0], "Ⅲ 4", "4. 기타 소비자의 구매선택 및 거래질서에 중대한 영향을 미치는 내용"),
    ("type_body", DESIGNATION_NOTICE[0], "5 라", DESIGNATION_PERFORMANCE),
    ("type_performance", DESIGNATION_NOTICE[0], "5 라", DESIGNATION_PERFORMANCE),
    ("type_ranking", DESIGNATION_NOTICE[0], "14 나",
     "자기자신이나 자기가 공급하는 상품(이하\"자기의 것\"이라 한다)이 경쟁사업자의 것보다 현저히 우량 또는 유리하다고 "
     "나타내기 위하여 \"최대\", \"최고\", \"최초\", \"제일\", \"유일\"등 배타성을 띤 절대적 표현의 용어를 사용하여 "
     "소비자를 오인시킬 우려가 있는 표시ㆍ광고행위는 부당한 표시ㆍ광고가 된다."),
    ("type_safety", "수상·인증 등의 표시·광고에 관한 심사지침", "Ⅴ 1",
     "1. 수상·인증·선정·특허 등의 사실이 없음에도 불구하고 이러한 사실이 있는 것처럼 표시·광고하는 행위는 "
     "부당한 표시·광고에 해당할 수 있다."),
    ("medicinal", "소비자 안전에 관한 표시·광고 심사지침", "Ⅴ 1 가",
     "의약품이 아닌 상품의 효능 등을 객관적 근거 없이 의약품의 효능이 있는 것처럼 사실과 다르게 소비자를 오인시킬 "
     "우려가 있는 표시·광고행위는 부당한 표시·광고가 된다."),
])
def test_근거_조문의_위치와_인용을_본문에서_읽는다(law: FakeLaw, key, law_name, article, quoted):
    source = _pick(load_advertising_evidence(law, AS_OF), key)

    assert (source.law_name, source.article, source.quoted_text) == (law_name, article, quoted)
    assert source.is_mock is False


def test_근거에_적용_판의_링크와_시행일이_붙는다(law: FakeLaw):
    evidence = load_advertising_evidence(law, AS_OF)

    assert evidence.article_5.source_url == "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=268659"
    assert evidence.article_5.effective_date == "20250121"
    target = evidence.substantiation_targets[RiskType.BODY_EFFECT]
    assert target.source_url == "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000284664"
    assert target.effective_date == "20260903"
    assert [document["version_id"] for document in evidence.documents()] == [
        "268659", "2100000184414", "2100000284664", "2100000070475", "2100000056062"]


def _revise_substantiation(law: FakeLaw, *, enforce_date: str = "20261101") -> None:
    """실증 운영 고시에 개정 판을 더한다. 1번 항목의 문구가 바뀌고 시행일은 enforce_date."""
    name, rule_id = SUBSTANTIATION_NOTICE
    current = law.notice_search[name].items[0]
    law.notice_search[name] = type(law.notice_search[name])(total_count=2, items=[
        current.model_dump(), dict(rule_id=rule_id, name=name, serial_number="2100000999999",
                                   enforce_date=enforce_date, issue_date=enforce_date)])
    old = law.notice_bodies[current.serial_number].articles[0].article_content
    revised = old.replace("1. 인체에 직접적으로 영향을 미친다는 내용", "1. 인체에 직접적으로 영향을 미친다는 내용 및 건강 효능")
    assert revised != old
    law.notice_bodies["2100000999999"] = law.notice_body(SUBSTANTIATION_NOTICE, "2100000999999", enforce_date, revised)


def test_개정_판이_시행되면_바뀐_문구와_새_링크를_쓴다(law: FakeLaw):
    _revise_substantiation(law)

    source = load_advertising_evidence(law, date(2026, 11, 1)).substantiation_targets[RiskType.BODY_EFFECT]

    assert source.quoted_text == "1. 인체에 직접적으로 영향을 미친다는 내용 및 건강 효능"
    assert source.source_url.endswith("admRulSeq=2100000999999")
    assert source.effective_date == "20261101"


def test_개정_판이_시행되기_전에는_현행_판을_쓴다(law: FakeLaw):
    _revise_substantiation(law)

    source = load_advertising_evidence(law, date(2026, 10, 31)).substantiation_targets[RiskType.BODY_EFFECT]

    assert source.quoted_text == "1. 인체에 직접적으로 영향을 미친다는 내용"
    assert source.source_url.endswith("admRulSeq=2100000284664")


def _edit_notice(law: FakeLaw, old: str, new: str) -> None:
    body = law.notice_bodies["2100000284664"]
    text = body.articles[0].article_content
    assert old in text
    law.notice_bodies["2100000284664"] = law.notice_body(SUBSTANTIATION_NOTICE, "2100000284664", "20260903",
                                                         text.replace(old, new))


def test_개정으로_표지_문구가_사라지면_옛_문구를_내지_않고_알린다(law: FakeLaw):
    _edit_notice(law, "1. 인체에 직접적으로", "1. 사람 몸에 직접")

    with pytest.raises(EvidenceUnavailable, match="Ⅲ 1"):
        load_advertising_evidence(law, AS_OF)


def test_표지_문구로_시작하는_줄이_둘이면_임의로_고르지_않는다(law: FakeLaw):
    _edit_notice(law, "1. 인체에 직접적으로 영향을 미친다는 내용",
                 "1. 인체에 직접적으로 영향을 미친다는 내용\n1. 인체에 직접적으로 닿는 내용")

    with pytest.raises(EvidenceUnavailable, match="Ⅲ 1"):
        load_advertising_evidence(law, AS_OF)
