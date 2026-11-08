"""표시·광고 근거 조문을 기준일 판 본문에서 읽는다.

- 법률은 조·항으로, 본문이 한 덩어리인 고시·지침은 표지 문구로 시작하는 줄로 찾는다.
- 줄의 나머지가 개정되면 인용도 따라 바뀐다. 표지 문구가 사라지면 옛 문구를 내지 않고 EvidenceUnavailable로 알린다.
"""

from dataclasses import dataclass
from datetime import date

from ...schemas.schemas import LegalSource
from ..common.law import (
    DocRef, EvidenceUnavailable, LawDocument, LawLookup, compact, law_paragraph, load_admrul, load_law,
    normalize_text,
)
from .schemas import AdvertisingRiskType

# (문서 이름, 법령ID·행정규칙ID)
LAW_ACT = ("표시ㆍ광고의 공정화에 관한 법률", "002011")
DESIGNATION_NOTICE = ("부당한 표시·광고행위의 유형 및 기준 지정고시", "34717")
SUBSTANTIATION_NOTICE = ("표시ㆍ광고 내용의 실증에 관한 운영 고시", "20246")
AWARD_CERT_GUIDELINE = ("수상·인증 등의 표시·광고에 관한 심사지침", "35034")
CONSUMER_SAFETY_GUIDELINE = ("소비자 안전에 관한 표시·광고 심사지침", "35091")

# 항목 앞의 목록 표시. 소비자 안전 심사지침 Ⅴ 1 가의 문장이 "- "로 시작함
_LIST_MARK = "- "


@dataclass(frozen=True)
class AdvertisingEvidence:
    """기준일에 적용되는 표시·광고 근거 조문 묶음.

    Attributes:
        article_3: 표시광고법 제3조 제1항.
        article_5: 표시광고법 제5조 제1항.
        substantiation_targets: 주장 유형별 실증 운영 고시 항목.
        type_sources: 주장 유형별 지정고시·심사지침 항목.
        medicinal_effect: 소비자 안전 심사지침의 의약품 효능 항목.
        recommendation: 지정고시 12 가(전문가·기관의 추천·권장 사실이 없는데 있는 것처럼). 추천 주장에 더한다.
        refs: 읽은 문서 버전.
    """

    article_3: LegalSource
    article_5: LegalSource
    substantiation_targets: dict[AdvertisingRiskType, LegalSource]
    type_sources: dict[AdvertisingRiskType, LegalSource]
    medicinal_effect: LegalSource
    recommendation: LegalSource
    refs: tuple[DocRef, ...]

    def documents(self) -> list[dict[str, str]]:
        """결과 query에 남길 문서 식별 정보.

        Returns:
            list[dict[str, str]]: 문서별 이름·문서 ID·버전 ID·시행일·열람 주소.
        """
        return [ref.describe() for ref in self.refs]


def _line_source(document: LawDocument, article: str, marker: str) -> LegalSource:
    """표지 문구로 시작하는 줄 하나를 근거로 만든다.

    Args:
        document: 본문이 한 덩어리인 행정규칙.
        article: 결과에 적을 조문 위치.
        marker: 줄의 시작 문구.

    Returns:
        LegalSource: 줄 전체를 인용한 근거.

    Raises:
        EvidenceUnavailable: 표지 문구로 시작하는 줄이 정확히 하나가 아닌 경우.
    """
    text = "\n".join(item.article_content or "" for item in document.body.articles)
    lines = [line.strip().removeprefix(_LIST_MARK) for line in text.splitlines()]
    matches = [line for line in lines if compact(line).startswith(compact(marker))]
    if len(matches) != 1:
        raise EvidenceUnavailable(f"{document.name} {article}의 '{marker}' 줄을 유일하게 찾지 못했습니다.")
    return document.ref.source(article, normalize_text(matches[0]))


def load_advertising_evidence(client: LawLookup, as_of: date) -> AdvertisingEvidence:
    """기준일에 적용되는 근거 조문을 읽는다.

    Args:
        client: 법제처 조회.
        as_of: 기준일.

    Returns:
        AdvertisingEvidence: 기준일 근거 묶음.

    Raises:
        EvidenceUnavailable: 판이나 조문을 확인하지 못한 경우.
    """
    law = load_law(client, name=LAW_ACT[0], law_id=LAW_ACT[1], as_of=as_of)
    designation = load_admrul(client, name=DESIGNATION_NOTICE[0], rule_id=DESIGNATION_NOTICE[1], as_of=as_of)
    substantiation = load_admrul(client, name=SUBSTANTIATION_NOTICE[0], rule_id=SUBSTANTIATION_NOTICE[1], as_of=as_of)
    award_cert = load_admrul(client, name=AWARD_CERT_GUIDELINE[0], rule_id=AWARD_CERT_GUIDELINE[1], as_of=as_of)
    consumer_safety = load_admrul(client, name=CONSUMER_SAFETY_GUIDELINE[0], rule_id=CONSUMER_SAFETY_GUIDELINE[1],
                                  as_of=as_of)
    performance = _line_source(designation, "5 라", "라. 표시ㆍ광고된 상품의 성능이나 효능이")
    return AdvertisingEvidence(
        article_3=law.ref.source("제3조 제1항", law_paragraph(law.body, 3, "①")),
        article_5=law.ref.source("제5조 제1항", law_paragraph(law.body, 5, "①")),
        substantiation_targets={
            AdvertisingRiskType.BODY_EFFECT: _line_source(substantiation, "Ⅲ 1", "1. 인체에 직접적으로"),
            AdvertisingRiskType.SAFETY_CERTIFICATION: _line_source(substantiation, "Ⅲ 2", "2. 안전 또는 환경"),
            AdvertisingRiskType.PERFORMANCE_QUALITY: _line_source(substantiation, "Ⅲ 3", "3. 성능, 효능, 품질에"),
            AdvertisingRiskType.RANKING_ABSOLUTE: _line_source(substantiation, "Ⅲ 4", "4. 기타 소비자의 구매선택"),
            # 원재료·성분은 실증 고시 Ⅲ 3의 예시("98% 유기농 고급원료")에 해당. 원산지·보증은 Ⅲ 4 기타 구매선택 사항
            AdvertisingRiskType.INGREDIENT_MATERIAL: _line_source(substantiation, "Ⅲ 3", "3. 성능, 효능, 품질에"),
            AdvertisingRiskType.ORIGIN_MAKER: _line_source(substantiation, "Ⅲ 4", "4. 기타 소비자의 구매선택"),
            AdvertisingRiskType.WARRANTY: _line_source(substantiation, "Ⅲ 4", "4. 기타 소비자의 구매선택"),
        },
        type_sources={
            AdvertisingRiskType.BODY_EFFECT: performance,
            AdvertisingRiskType.SAFETY_CERTIFICATION: _line_source(award_cert, "Ⅴ 1", "1. 수상·인증·선정·특허 등의 사실이"),
            AdvertisingRiskType.PERFORMANCE_QUALITY: performance,
            AdvertisingRiskType.RANKING_ABSOLUTE: _line_source(designation, "14 나", "자기자신이나 자기가 공급하는 상품"),
            AdvertisingRiskType.INGREDIENT_MATERIAL: _line_source(designation, "4 가", "가. 실제 사용되지 않는 원자재나 성분이"),
            AdvertisingRiskType.ORIGIN_MAKER: _line_source(designation, "10 나", "나. 외국에서 수입된 상품을 마치 국산품인 것처럼"),
            AdvertisingRiskType.WARRANTY: _line_source(designation, "11", "자기가 공급하는 상품 등에 관하여 보증"),
        },
        medicinal_effect=_line_source(consumer_safety, "Ⅴ 1 가", "의약품이 아닌 상품의 효능 등을 객관적 근거"),
        recommendation=_line_source(designation, "12 가", "가. 전문가, 연구기관, 유명단체에 의한 추천"),
        refs=(law.ref, designation.ref, substantiation.ref, award_cert.ref, consumer_safety.ref),
    )
