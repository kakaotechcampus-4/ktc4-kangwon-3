"""표시·광고 Tool의 근거 조문과 코드 규칙. 모델을 부르지 않는 상수·순수 함수만 둔다.

- 근거 조문: 표시광고법 제3조·제5조, 실증 운영 고시, 지정고시, 수상·인증 심사지침, 소비자 안전 심사지침.
  quoted_text는 tests/fixtures/advertising_law 원문과 같은지 테스트가 확인한다.
- KC 표기 찾기, 위험도, 근거 묶음, 판매 전 할 일 문구.
"""

import re

from ...schemas.advertising import AdvertisingClaim, AdvertisingRiskType
from ...schemas.schemas import LegalSource, RiskLevel

_SOURCE_NAME = "국가법령정보센터"
# 버전(MST·일련번호)을 고정한 공개 열람 주소. 요청 URL(OC 포함)은 쓰지 않는다.
_LAW_URL = "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=268659"
_DESIGNATION_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000184414"
_SUBSTANTIATION_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000284664"
_AWARD_CERT_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000070475"
_CONSUMER_SAFETY_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000056062"

_LAW_NAME = "표시ㆍ광고의 공정화에 관한 법률"
_DESIGNATION = "부당한 표시·광고행위의 유형 및 기준 지정고시"
_SUBSTANTIATION = "표시ㆍ광고 내용의 실증에 관한 운영 고시"
_AWARD_CERT = "수상·인증 등의 표시·광고에 관한 심사지침"
_CONSUMER_SAFETY = "소비자 안전에 관한 표시·광고 심사지침"


def _source(law_name: str, article: str, quoted_text: str, url: str, effective_date: str) -> LegalSource:
    return LegalSource(
        source_name=_SOURCE_NAME, law_name=law_name, article=article, quoted_text=quoted_text,
        source_url=url, effective_date=effective_date, is_mock=False,
    )


# quoted_text는 픽스처 원문에서 그대로 옮겼다(test_advertising_sources가 대조).
LAW_ARTICLE_3 = _source(
    _LAW_NAME, "제3조 제1항",
    "① 사업자등은 소비자를 속이거나 소비자로 하여금 잘못 알게 할 우려가 있는 표시ㆍ광고 행위로서 공정한 거래질서를 "
    "해칠 우려가 있는 다음 각 호의 행위를 하거나 다른 사업자등으로 하여금 하게 하여서는 아니 된다.",
    _LAW_URL, "2025-01-21",
)
LAW_ARTICLE_5 = _source(
    _LAW_NAME, "제5조 제1항",
    "① 사업자등은 자기가 한 표시ㆍ광고 중 사실과 관련한 사항에 대하여는 실증(實證)할 수 있어야 한다.",
    _LAW_URL, "2025-01-21",
)
SUBSTANTIATION_TARGETS = {
    AdvertisingRiskType.BODY_EFFECT: _source(
        _SUBSTANTIATION, "Ⅲ 1", "1. 인체에 직접적으로 영향을 미친다는 내용", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.SAFETY_CERTIFICATION: _source(
        _SUBSTANTIATION, "Ⅲ 2", "2. 안전 또는 환경, 신기술과 관련된 내용인 경우", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.PERFORMANCE_QUALITY: _source(
        _SUBSTANTIATION, "Ⅲ 3", "3. 성능, 효능, 품질에 관한 내용인 경우", _SUBSTANTIATION_URL, "2026-09-03"),
    AdvertisingRiskType.RANKING_ABSOLUTE: _source(
        _SUBSTANTIATION, "Ⅲ 4", "4. 기타 소비자의 구매선택 및 거래질서에 중대한 영향을 미치는 내용",
        _SUBSTANTIATION_URL, "2026-09-03"),
}
TYPE_SOURCES = {
    AdvertisingRiskType.BODY_EFFECT: _source(
        _DESIGNATION, "5 라",
        "라. 표시ㆍ광고된 상품의 성능이나 효능이 객관적으로 확인될 수 없거나 확인되지 아니하였는데도 불구하고 "
        "확실하게 발휘되는 것처럼 표시ㆍ광고하는 행위",
        _DESIGNATION_URL, "2019-12-12"),
    AdvertisingRiskType.SAFETY_CERTIFICATION: _source(
        _AWARD_CERT, "Ⅴ 1",
        "1. 수상·인증·선정·특허 등의 사실이 없음에도 불구하고 이러한 사실이 있는 것처럼 표시·광고하는 행위는 "
        "부당한 표시·광고에 해당할 수 있다.",
        _AWARD_CERT_URL, "2016-12-23"),
    AdvertisingRiskType.PERFORMANCE_QUALITY: _source(
        _DESIGNATION, "5 라",
        "라. 표시ㆍ광고된 상품의 성능이나 효능이 객관적으로 확인될 수 없거나 확인되지 아니하였는데도 불구하고 "
        "확실하게 발휘되는 것처럼 표시ㆍ광고하는 행위",
        _DESIGNATION_URL, "2019-12-12"),
    AdvertisingRiskType.RANKING_ABSOLUTE: _source(
        _DESIGNATION, "14 나",
        "자기자신이나 자기가 공급하는 상품(이하\"자기의 것\"이라 한다)이 경쟁사업자의 것보다 현저히 우량 또는 유리하다고 "
        "나타내기 위하여 \"최대\", \"최고\", \"최초\", \"제일\", \"유일\"등 배타성을 띤 절대적 표현의 용어를 사용하여 "
        "소비자를 오인시킬 우려가 있는 표시ㆍ광고행위는 부당한 표시ㆍ광고가 된다.",
        _DESIGNATION_URL, "2019-12-12"),
}
MEDICINAL_EFFECT_SOURCE = _source(
    _CONSUMER_SAFETY, "Ⅴ 1 가",
    "의약품이 아닌 상품의 효능 등을 객관적 근거 없이 의약품의 효능이 있는 것처럼 사실과 다르게 소비자를 오인시킬 "
    "우려가 있는 표시·광고행위는 부당한 표시·광고가 된다.",
    _CONSUMER_SAFETY_URL, "2016-08-03",
)

# 의약품 효능처럼 읽히는 낱말. 소비자 안전 지침 Ⅴ 1 가가 "부당한 표시·광고가 된다"로 단정하는 유형이라 위험도를 높인다.
_MEDICINAL_WORDS = ("치료", "예방", "완치", "질병", "질환")

# 국내 인증(KC) 표기. 실제 인증 여부는 상품 글만으로 알 수 없어 모델 판단과 관계없이 코드가 찾아 확인을 안내한다.
# "KC 인증정보"는 AliExpress 사양 칸 이름이라 뺀다(값이 "확인되지 않음"인 경우가 있다).
# "KC 인증 없음"·"KC 인증을 받지 않은"처럼 인증이 없다는 문장은 인증 주장이 아니라 뺀다.
_KC_MARK = re.compile(r"(?<![A-Za-z])KC\s*(?:인증(?!정보)|마크|안전인증|안전확인|공급자적합성|방송통신|적합성평가|certifi\w*)"
                      r"(?!\s*(?:이|을|은)?\s*(?:없|받지\s*않|미))",
                      re.IGNORECASE)
_KC_REASON = "국내 인증(KC) 표기다. 실제로 인증을 받은 제품인지 상품 글만으로는 확인할 수 없다."

TYPE_LABELS = {
    AdvertisingRiskType.BODY_EFFECT: "인체 효능·효과",
    AdvertisingRiskType.SAFETY_CERTIFICATION: "안전·인증",
    AdvertisingRiskType.PERFORMANCE_QUALITY: "성능·품질",
    AdvertisingRiskType.RANKING_ABSOLUTE: "순위·절대적 표현",
}
RISK_ORDER = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)


def normalize(text: str) -> str:
    """대조용 정규화. 공백 차이와 영문 대소문자만 무시한다. 글자를 바꾼 인용은 그대로 다르게 본다."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def find_kc_claims(lines: list[str]) -> list[AdvertisingClaim]:
    """국내 인증(KC) 표기를 찾는다. 같은 표기는 한 번만 돌려준다."""
    found: dict[str, AdvertisingClaim] = {}
    for line in lines:
        for match in _KC_MARK.finditer(line):
            quote = match.group(0)
            found.setdefault(normalize(quote), AdvertisingClaim(
                quote=quote, risk_type=AdvertisingRiskType.SAFETY_CERTIFICATION, reason=_KC_REASON))
    return list(found.values())


def _is_certification(claim: AdvertisingClaim) -> bool:
    return claim.risk_type is AdvertisingRiskType.SAFETY_CERTIFICATION and (
        "인증" in claim.quote or _KC_MARK.search(claim.quote) is not None)


def claim_risk(claim: AdvertisingClaim) -> RiskLevel:
    if claim.risk_type is AdvertisingRiskType.BODY_EFFECT and any(word in claim.quote for word in _MEDICINAL_WORDS):
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def sources_for(claim: AdvertisingClaim, risk_level: RiskLevel) -> list[LegalSource]:
    sources = [LAW_ARTICLE_3, LAW_ARTICLE_5, SUBSTANTIATION_TARGETS[claim.risk_type], TYPE_SOURCES[claim.risk_type]]
    if risk_level is RiskLevel.HIGH:
        sources.append(MEDICINAL_EFFECT_SOURCE)
    return sources


def claim_action(claim: AdvertisingClaim, risk_level: RiskLevel) -> str:
    if _is_certification(claim):
        return (f"'{claim.quote}' 표기가 있습니다. 실제로 인증을 받은 제품인지 인증번호와 인증서로 확인하고, "
                "확인되지 않으면 표기를 빼세요.")
    if risk_level is RiskLevel.HIGH:
        return (f"'{claim.quote}'는 의약품 효능처럼 읽힙니다. 의약품이 아닌 상품이면 문구를 빼거나 고치고, "
                "남기려면 객관적 근거 자료를 먼저 확인하세요.")
    return f"'{claim.quote}'를 뒷받침하는 시험·조사 자료(실증자료)를 준비하거나, 자료가 없으면 문구를 빼거나 고치세요."
