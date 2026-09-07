"""개발용 더미 FinalAssessment 팩토리. 파이프라인 연결 후 제거한다."""

from ..schemas.product import Attribute, Product
from ..schemas.schemas import (
    AdvertisingAssessment,
    AdvertisingPhrase,
    ChildrenAssessment,
    CustomsAssessment,
    Determination,
    ElectricalAssessment,
    FinalAssessment,
    FinalVerificationStatus,
    LegalSource,
    OverallStatus,
    RadioAssessment,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)


def build_dummy_assessment(product_id: str) -> FinalAssessment:
    """RC 보트 기반 더미 진단 결과를 생성한다.

    Args:
        product_id: 요청에서 넘어온 상품 식별자.

    Returns:
        6개 툴 결과가 채워진 FinalAssessment.
    """
    product = Product(
        product_id=product_id,
        product_name="사이버 펑크 고속 RC 보트 2.4GHz 방수 듀얼 모터 충전식 배터리",
        category="RC 보트 / 원격조종 완구",
        intended_use="수영장·호수에서 원격조종 수상 놀이",
        target_age="NOT SUITABLE FOR CHILDREN UNDER 6 YEARS DUE TO SMALL PIECES",
        electrical_powered=True,
        wireless_comm=True,
        battery_included=True,
        battery_is_the_product=False,
        heating=False,
        food_contact=False,
        medical_claim=False,
        cosmetic_claim=False,
        weapon_like=False,
        plant_material=False,
        chemical_product=False,
        for_children=True,
        listing_text=[
            "사이버 펑크 고속 RC 보트 2.4GHz 방수 듀얼 모터 충전식 배터리 수영장 호수 소년 어린이 성인 생일 선물",
            "2.4GHz 주파수를 사용한 안정적인 원격 조종 기능",
        ],
        attributes=[
            Attribute(name="통신방식", value="2.4GHz RF"),
            Attribute(name="배터리종류", value="리튬이온 3.7V"),
            Attribute(name="모터", value="듀얼 모터"),
            Attribute(name="모델번호", value="H4202-2"),
        ],
    )

    tool_results = [
        ToolResult(
            tool_name=ToolName.CUSTOMS,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="수입품이므로 HS 코드 확인 및 세관장확인 요건 조회 필요",
            result=CustomsAssessment(
                hs_code_candidates=["9503.00", "8906.90"],
                customs_confirmation_required=True,
                applicable_requirements=["세관장확인 대상 여부 확인 필요"],
                required_documents=["수입신고서", "KC 인증서"],
                legal_sources=[
                    LegalSource(source_name="관세법", law_name="관세법", article="제226조", is_mock=True)
                ],
            ),
            findings=[
                RegulatoryFinding(
                    tool_name=ToolName.CUSTOMS,
                    subject="HS 코드 분류",
                    determination=Determination.POSSIBLY_REQUIRED,
                    risk_level=RiskLevel.MEDIUM,
                    summary="완구(9503) 또는 보트(8906) 분류에 따라 세관장확인 요건이 달라짐",
                    rationale="RC 보트는 완구와 선박 모두에 해당할 수 있어 정확한 HS 분류 필요",
                    requirements=["HS 코드 확정 후 세관장확인 요건 재조회"],
                )
            ],
        ),
        ToolResult(
            tool_name=ToolName.RADIO,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="2.4GHz 무선통신 사용 → 전파법 적합성평가 대상 여부 확인 필요",
            result=RadioAssessment(
                wireless_features=["2.4GHz RF 원격조종"],
                frequency_bands=["2.4GHz ISM"],
                conformity_assessment_required=True,
                certification_type="적합인증",
                legal_sources=[
                    LegalSource(source_name="전파법", law_name="전파법", article="제58조의2", is_mock=True)
                ],
            ),
            findings=[
                RegulatoryFinding(
                    tool_name=ToolName.RADIO,
                    subject="전파 적합성평가",
                    determination=Determination.REQUIRED,
                    risk_level=RiskLevel.HIGH,
                    summary="2.4GHz 무선기기 → KC 적합성평가(적합인증) 필수",
                    rationale="2.4GHz RF 송수신 기능이 있으므로 방송통신기자재 적합성평가 대상",
                    requirements=["KC 적합인증 취득", "RRA 인증번호 표시"],
                )
            ],
        ),
        ToolResult(
            tool_name=ToolName.FOOD_DRUG,
            status=ToolStatus.NOT_APPLICABLE,
            selected=False,
            selection_reason="음식접촉·피부접촉·의료효능·미용효과 해당사항 없음",
        ),
        ToolResult(
            tool_name=ToolName.ELECTRICAL,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="전기 모터 + 리튬 배터리 내장 → 전안법 대상 여부 확인 필요",
            result=ElectricalAssessment(
                power_sources=["리튬이온 3.7V 충전식 배터리"],
                rated_specifications=["3.7V"],
                safety_management_required=True,
                certification_type="안전확인",
                legal_sources=[
                    LegalSource(
                        source_name="전안법",
                        law_name="전기용품 및 생활용품 안전관리법",
                        article="제15조",
                        is_mock=True,
                    )
                ],
            ),
            findings=[
                RegulatoryFinding(
                    tool_name=ToolName.ELECTRICAL,
                    subject="리튬이차전지 안전확인",
                    determination=Determination.REQUIRED,
                    risk_level=RiskLevel.HIGH,
                    summary="리튬이차전지 내장 → KC 안전확인 대상",
                    rationale="전안법 시행규칙 별표에 리튬이차단전지가 안전인증 대상 품목으로 등재",
                    requirements=["KC 안전확인 신고", "안전기준 적합 시험성적서"],
                )
            ],
        ),
        ToolResult(
            tool_name=ToolName.CHILDREN,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="상품명에 '어린이' 포함, 완구 형태 → 어린이제품법 대상 여부 확인 필요",
            result=ChildrenAssessment(
                target_age_raw="NOT SUITABLE FOR CHILDREN UNDER 6 YEARS DUE TO SMALL PIECES",
                intended_for_children=True,
                product_type="완구",
                safety_management_required=True,
                certification_type="안전확인",
                legal_sources=[
                    LegalSource(
                        source_name="어린이제품법",
                        law_name="어린이제품 안전 특별법",
                        article="제17조",
                        is_mock=True,
                    )
                ],
            ),
            findings=[
                RegulatoryFinding(
                    tool_name=ToolName.CHILDREN,
                    subject="어린이제품 안전확인",
                    determination=Determination.REQUIRED,
                    risk_level=RiskLevel.HIGH,
                    summary="완구 → 어린이제품 안전확인 대상",
                    rationale="13세 이하 어린이가 사용 대상이며 완구에 해당하므로 안전확인 필수",
                    requirements=["어린이제품 안전확인 신고", "어린이제품 공통안전기준 적합"],
                )
            ],
        ),
        ToolResult(
            tool_name=ToolName.LABEL_AD,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="수입 판매 시 전자상거래 표시의무 확인 필요",
            result=AdvertisingAssessment(
                reviewed_phrases=["사이버 펑크 고속 RC 보트", "방수", "소년 어린이 성인 생일 선물"],
                detected_phrases=[
                    AdvertisingPhrase(
                        text="방수",
                        risk_type="성능 표방",
                        risk_level=RiskLevel.LOW,
                        reason="방수 등급(IPX) 미표기 시 과장광고 소지",
                    )
                ],
                overall_risk=RiskLevel.LOW,
                legal_sources=[
                    LegalSource(
                        source_name="전자상거래법",
                        law_name="전자상거래 등에서의 소비자보호에 관한 법률",
                        is_mock=True,
                    )
                ],
            ),
            findings=[
                RegulatoryFinding(
                    tool_name=ToolName.LABEL_AD,
                    subject="표시광고 검토",
                    determination=Determination.POSSIBLY_REQUIRED,
                    risk_level=RiskLevel.LOW,
                    summary="'방수' 표현에 대한 IPX 등급 표기 권장",
                    rationale="방수 성능 등급 없이 '방수' 표기 시 과장광고 소지 있음",
                    requirements=["완구류 필수 표시사항 기재", "방수 등급 명시 권장"],
                )
            ],
        ),
    ]

    all_findings = []
    for tr in tool_results:
        all_findings.extend(tr.findings)

    return FinalAssessment(
        assessment_id=f"dummy-{product_id}",
        product=product,
        verification_status=FinalVerificationStatus.VERIFIED_WITH_WARNINGS,
        overall_status=OverallStatus.ACTION_REQUIRED,
        summary=(
            "2.4GHz 무선 RC 보트로, 전파법(적합인증), 전안법(리튬전지 안전확인), "
            "어린이제품법(완구 안전확인) 3개 법령의 KC 인증이 필요합니다. "
            "HS 코드 분류에 따라 세관장확인 요건이 추가될 수 있습니다."
        ),
        selected_tools=[
            ToolName.CUSTOMS,
            ToolName.RADIO,
            ToolName.ELECTRICAL,
            ToolName.CHILDREN,
            ToolName.LABEL_AD,
        ],
        tool_results=tool_results,
        findings=all_findings,
        required_actions=[
            "KC 적합인증 취득 (전파법, 2.4GHz 무선기기)",
            "KC 안전확인 신고 (전안법, 리튬이차전지)",
            "어린이제품 안전확인 신고 (어린이제품법, 완구)",
            "HS 코드 확정 후 세관장확인 요건 재조회",
            "전자상거래 상품정보 제공 고시 필수 표시사항 기재",
        ],
        missing_information=[
            "정확한 HS 코드 분류 (완구 9503 vs 선박 8906)",
            "방수 등급 (IPX 미표기)",
        ],
        verification=VerificationResult(
            status=VerificationStatus.APPROVED_WITH_WARNINGS,
            review_summary="주요 규제 3건 식별 완료. HS 분류 미확정으로 세관 요건은 재확인 필요.",
            checked_finding_ids=[f.finding_id for f in all_findings],
        ),
    )
