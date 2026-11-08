"""표시·광고 Tool의 코드 규칙. 모델을 부르지 않는 상수·순수 함수만 둔다.

KC 표기 찾기, 위험도, 근거 묶음, 판매 전 할 일 문구. 근거 조문 자체는 evidence.py가 적용 판 본문에서 읽는다.
"""

import re

from ...schemas.schemas import LegalSource, RiskLevel
from ..common.facts import object_particle, topic_particle
from .evidence import AdvertisingEvidence
from .schemas import AdvertisingClaim, AdvertisingRiskType

# 의약품 효능처럼 읽히는 낱말. 소비자 안전 지침 Ⅴ 1 가가 "부당한 표시·광고가 된다"로 단정하는 유형이라 위험도를 높인다.
_MEDICINAL_WORDS = ("치료", "예방", "완치", "질병", "질환")
# 영문 인증 표기. 'Certified 3C CCC', 'CE Certified', 'FDA 승인'처럼 외국 인증을 받았다는 표기도 인증 확인 안내로 보낸다
# (2026-11-08: 실증자료 안내로 잘못 나가던 문제). 'Ceramic'처럼 낱말 안의 글자는 제외
# 추천·권장 주장. 인증·수상과 같은 유형이지만 근거 조문은 지정고시 12 가(전문가·기관 추천)가 정확해 함께 붙인다
_RECOMMEND = re.compile(r"추천|권장|recommend", re.IGNORECASE)
_FOREIGN_CERT = re.compile(r"certif|(?<![A-Za-z])(?:CE|CCC|3C|RoHS|FCC|FDA|UL|CB|GS|TÜV|TUV)(?![A-Za-z])", re.IGNORECASE)

# 국내 인증(KC) 표기. 실제 인증 여부는 상품 글만으로 알 수 없어 모델 판단과 관계없이 코드가 찾아 확인을 안내한다.
# "KC 인증정보"는 AliExpress 사양 칸 이름이라 뺀다(값이 "확인되지 않음"인 경우가 있다).
# "KC 인증 없음"·"KC 인증을 받지 않은"처럼 인증이 없다는 문장은 인증 주장이 아니라 뺀다.
_KC_MARK = re.compile(r"(?<![A-Za-z])KC\s*(?:인증(?!정보)|마크|안전인증|안전확인|공급자적합성|방송통신|적합성평가|certifi\w*)"
                      r"(?!\s*(?:이|을|은)?\s*(?:없|받지\s*않|미))",
                      re.IGNORECASE)
_KC_REASON = "국내 인증(KC) 표기다. 실제로 인증을 받은 제품인지 상품 글만으로는 확인할 수 없다."

# 판단 제목·요약에 쓰는 유형 이름 (판매자 화면에 나가므로 가운뎃점 대신 띄어쓰기)
TYPE_LABELS = {
    AdvertisingRiskType.BODY_EFFECT: "인체 효능",
    AdvertisingRiskType.SAFETY_CERTIFICATION: "인증 수상",
    AdvertisingRiskType.PERFORMANCE_QUALITY: "성능 품질",
    AdvertisingRiskType.INGREDIENT_MATERIAL: "원재료 성분",
    AdvertisingRiskType.ORIGIN_MAKER: "원산지 제조자",
    AdvertisingRiskType.RANKING_ABSOLUTE: "절대 표현",
    AdvertisingRiskType.WARRANTY: "보증 약속",
}
RISK_ORDER = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)


def normalize(text: str) -> str:
    """대조용 정규화. 공백 차이와 영문 대소문자만 무시한다. 글자를 바꾼 인용은 그대로 다르게 본다.

    Args:
        text: 원문 또는 인용.

    Returns:
        str: 공백을 하나로 모으고 소문자로 바꾼 글.
    """
    return re.sub(r"\s+", " ", text).strip().casefold()


def find_kc_claims(lines: list[str]) -> list[AdvertisingClaim]:
    """국내 인증(KC) 표기를 찾는다. 같은 표기는 한 번만 돌려준다.

    Args:
        lines: 판매자 문구.

    Returns:
        list[AdvertisingClaim]: 안전·인증 유형의 KC 표기 주장.
    """
    found: dict[str, AdvertisingClaim] = {}
    for line in lines:
        for match in _KC_MARK.finditer(line):
            quote = match.group(0)
            found.setdefault(normalize(quote), AdvertisingClaim(
                quote=quote, risk_type=AdvertisingRiskType.SAFETY_CERTIFICATION, reason=_KC_REASON))
    return list(found.values())


def _is_certification(claim: AdvertisingClaim) -> bool:
    """인증 표기 주장인지 본다.

    Args:
        claim: 검토한 주장.

    Returns:
        bool: 안전·인증 유형이고 인용에 "인증"이나 KC 표기가 있으면 True.
    """
    return claim.risk_type is AdvertisingRiskType.SAFETY_CERTIFICATION and (
        "인증" in claim.quote or _KC_MARK.search(claim.quote) is not None
        or _FOREIGN_CERT.search(claim.quote) is not None)


def claim_risk(claim: AdvertisingClaim) -> RiskLevel:
    """주장의 위험도. 의약품 효능처럼 읽히는 인체 효능 주장만 높게 본다.

    Args:
        claim: 검토한 주장.

    Returns:
        RiskLevel: HIGH 또는 MEDIUM.
    """
    if claim.risk_type is AdvertisingRiskType.BODY_EFFECT and any(word in claim.quote for word in _MEDICINAL_WORDS):
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def sources_for(evidence: AdvertisingEvidence, claim: AdvertisingClaim, risk_level: RiskLevel) -> list[LegalSource]:
    """주장 하나에 붙일 근거 조문을 모은다.

    Args:
        evidence: 적용 판 근거 조문.
        claim: 검토한 주장.
        risk_level: 주장의 위험도. HIGH면 소비자 안전 심사지침을 더함.

    Returns:
        list[LegalSource]: 법 제3조·제5조 → 실증 대상 → 유형별 지침 순.
    """
    sources = [evidence.article_3, evidence.article_5, evidence.substantiation_targets[claim.risk_type],
               evidence.type_sources[claim.risk_type]]
    if risk_level is RiskLevel.HIGH:
        sources.append(evidence.medicinal_effect)
    if claim.risk_type is AdvertisingRiskType.SAFETY_CERTIFICATION and _RECOMMEND.search(claim.quote):
        sources.append(evidence.recommendation)
    return sources


def display_quote(claim: AdvertisingClaim) -> str:
    """판매자에게 보여 줄 인용. 영문·외국어면 번역을 괄호로 붙인다: 'Sunburn Relief'(햇볕 화상 완화)."""
    return f"'{claim.quote}'({claim.translation})" if claim.translation else f"'{claim.quote}'"


def _particle_word(claim: AdvertisingClaim) -> str:
    """조사를 정할 낱말. 번역이 붙으면 번역의 받침을 따른다."""
    return claim.translation or claim.quote


def claim_action(claim: AdvertisingClaim, risk_level: RiskLevel) -> str:
    """주장 하나에 대해 판매 전에 할 일.

    Args:
        claim: 검토한 주장.
        risk_level: 주장의 위험도.

    Returns:
        str: 인증 확인, 의약품 효능 문구 수정, 실증자료 준비 중 하나의 안내.
    """
    shown, word = display_quote(claim), _particle_word(claim)
    if _is_certification(claim):
        return (f"{shown} 표기가 있습니다. 실제로 인증을 받은 제품인지 인증번호와 인증서로 확인하고, "
                "확인되지 않으면 표기를 빼세요.")
    if claim.risk_type is AdvertisingRiskType.WARRANTY:
        return (f"{shown} 보증 약속이 있습니다. 보증 주체, 기간, 범위를 밝히고 실제로 지킬 수 있는지 확인하세요. "
                "지키기 어려우면 문구를 빼거나 고치세요.")
    if claim.risk_type is AdvertisingRiskType.ORIGIN_MAKER:
        return (f"{shown} 표기가 있습니다. 원산지나 제조자, 정품 여부가 사실인지 수입 서류로 확인하고, "
                "다르면 표기를 고치세요.")
    if risk_level is RiskLevel.HIGH:
        return (f"{shown}{topic_particle(word)} 의약품 효능처럼 읽힙니다. 의약품이 아닌 상품이면 문구를 빼거나 고치고, "
                "남기려면 객관적 근거 자료를 먼저 확인하세요.")
    return (f"{shown}{object_particle(word)} 뒷받침하는 시험·조사 자료(실증자료)를 준비하거나, "
            "자료가 없으면 문구를 빼거나 고치세요.")
