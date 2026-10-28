"""상품 케이스별 더미 진단 데이터. 질문 회차·선택 Tool 수·분야 카드 상태·결과 상태·실패를 골고루 덮음.

| 케이스 | 질문 회차 | 선택 Tool | 결말 |
| kc_fan | 0 | 전기 1개 | 대행 구매 가능 |
| power_bank | 1 | 전기·관세 | 직구 인증 필요 |
| rc_boat | 2 | 5개 (식품 건너뜀) | 직구 인증 필요 |
| charging_pad | 1 (2문항) | 전파 실패·전기 | 재확인 필요 (미완료 카드) |
| toy_gun | 0 | 어린이·표시광고 부분 성공 | 직구 인증 필요 (미완료 카드, 총 모양 신호보다 인증 필요가 먼저) |
| tumbler | 2 | 식품 1개 | 직구 인증 필요 |
| diffuser | 0 | 없음 | 완료, 재확인 필요 (지원 분야 밖: 화학제품) |
| question_limit | 3 → 한도 초과 | 전파·전기 | 재확인 필요 (세션이 미완료로 바꿈) |
| failed | 0 | - | 첫 실행 실패 |
| failed_after_answer | 1 | - | 답변 뒤 실패 |
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from ..routers._dummy import build_dummy_assessment
from ..schemas.callback import PublicQuestionDto
from ..schemas.product import Product
from ..schemas.schemas import (
    Determination,
    ExecutionEndReason,
    FinalAssessment,
    FinalVerificationStatus,
    LegalSource,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)


class DummyCaseName(StrEnum):
    """더미 상품 케이스."""

    KC_FAN = "kc_fan"
    POWER_BANK = "power_bank"
    RC_BOAT = "rc_boat"
    CHARGING_PAD = "charging_pad"
    TOY_GUN = "toy_gun"
    TUMBLER = "tumbler"
    DIFFUSER = "diffuser"
    QUESTION_LIMIT = "question_limit"
    FAILED = "failed"
    FAILED_AFTER_ANSWER = "failed_after_answer"


@dataclass(frozen=True)
class DummyCase:
    """더미 케이스 하나.

    Attributes:
        rounds: 회차별 질문. 회차마다 새 키만.
        fails: 질문을 다 받은 뒤 완료 대신 실패하는지.
        build: 상품 ID → 완료 결과. 질문 대기 결과의 바탕으로도 씀.
    """

    rounds: list[list[PublicQuestionDto]]
    fails: bool
    build: Callable[[str], FinalAssessment]


def _question(key: str, order: int, text: str, help_text: str | None = None) -> PublicQuestionDto:
    return PublicQuestionDto(question_key=key, question_order=order, question_text=text, help_text=help_text)


def _finding(
    tool: ToolName, subject: str, determination: Determination, risk: RiskLevel, summary: str, rationale: str,
    law_name: str, article: str | None = None,
) -> RegulatoryFinding:
    return RegulatoryFinding(
        tool_name=tool, subject=subject, determination=determination, risk_level=risk, summary=summary,
        rationale=rationale, legal_sources=[LegalSource(source_name=law_name, law_name=law_name, article=article)],
    )


def _ran(tool: ToolName, reason: str, *findings: RegulatoryFinding, status: ToolStatus = ToolStatus.SUCCESS,
         error: str | None = None) -> ToolResult:
    return ToolResult(
        tool_name=tool, status=status, selected=True, selection_reason=reason, findings=list(findings), error=error,
    )


def _assessment(
    product: Product,
    ran: list[ToolResult],
    *,
    overall: OverallStatus,
    summary: str,
    required_actions: list[str] | None = None,
    missing_information: list[str] | None = None,
    incomplete: ExecutionEndReason | None = None,
) -> FinalAssessment:
    """실행한 Tool 결과로 진단 결과를 만든다. 실행하지 않은 분야는 건너뜀으로 채움.

    Args:
        incomplete: 미완료 종료 사유. 없으면 완료(검증 통과).
    """
    by_tool = {tool_result.tool_name: tool_result for tool_result in ran}
    tool_results = [
        by_tool.get(tool) or ToolResult(
            tool_name=tool, status=ToolStatus.SKIPPED, selected=False, selection_reason="(더미) 해당 사항 없음",
        )
        for tool in ToolName
    ]
    findings = [finding for tool_result in ran for finding in tool_result.findings]
    return FinalAssessment(
        assessment_id=f"dummy-{product.product_id}",
        product=product,
        verification_status=FinalVerificationStatus.INCOMPLETE if incomplete else FinalVerificationStatus.VERIFIED,
        termination_reason=incomplete or ExecutionEndReason.COMPLETED,
        overall_status=overall,
        summary=f"(더미) {summary}",
        selected_tools=[tool_result.tool_name for tool_result in ran],
        tool_results=tool_results,
        findings=findings,
        required_actions=required_actions or [],
        missing_information=missing_information or [],
        verification=VerificationResult(
            status=VerificationStatus.REVISION_REQUIRED if incomplete else VerificationStatus.APPROVED,
            checked_finding_ids=[finding.finding_id for finding in findings],
        ),
    )


def _kc_fan(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="핸디선풍기 KC인증 USB 탁상겸용 충전선풍기", category="휴대용 선풍기",
        electrical_powered=True, battery_included=True, wireless_comm=False,
        listing_text=["인증정보: KC 안전확인 (전기용품): XU101030-17003A"],
    )
    return _assessment(product, [
        _ran(ToolName.ELECTRICAL, "충전식 전기용품 → 전안법 대상 여부 확인", _finding(
            ToolName.ELECTRICAL, "전기용품 안전확인", Determination.NOT_REQUIRED, RiskLevel.LOW,
            "상세페이지에 KC 안전확인 번호가 있어 추가 인증 없이 판매 가능",
            "표기된 안전확인 번호가 제품안전정보센터 조회 결과와 일치", "전기용품 및 생활용품 안전관리법", "제15조",
        )),
    ], overall=OverallStatus.LIKELY_COMPLIANT, summary="KC 안전확인을 받은 선풍기라 구매대행으로 판매할 수 있습니다.")


def _power_bank(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="고속충전 보조배터리 10000mAh PD 20W", category="보조배터리",
        electrical_powered=True, battery_included=True, battery_is_the_product=True,
    )
    return _assessment(product, [
        _ran(ToolName.ELECTRICAL, "리튬이온 보조배터리 → 전안법 안전인증 대상 확인", _finding(
            ToolName.ELECTRICAL, "휴대용 리튬이차전지 안전인증", Determination.REQUIRED, RiskLevel.HIGH,
            "휴대용 리튬이차전지 → KC 안전인증 필수",
            "보조배터리는 안전인증 대상 품목이며 구매대행도 인증 표시가 필요", "전기용품 및 생활용품 안전관리법", "제5조",
        )),
        _ran(ToolName.CUSTOMS, "수입 통관 시 세관장확인 대상 확인", _finding(
            ToolName.CUSTOMS, "세관장확인", Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM,
            "HS 8507.60 리튬이온 축전지 → 세관장확인 대상일 수 있음",
            "안전인증 대상 전기용품은 통관 때 인증 확인을 받음", "관세법", "제226조",
        )),
    ], overall=OverallStatus.ACTION_REQUIRED, summary="보조배터리는 KC 안전인증을 받아야 판매할 수 있습니다.",
        required_actions=["KC 안전인증 취득 (리튬이차전지)", "통관 시 세관장확인 서류 준비"])


def _charging_pad(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="15W 고속 무선충전패드 Qi 호환", category="무선충전기",
        electrical_powered=True, wireless_charging=True,
    )
    return _assessment(product, [
        _ran(ToolName.RADIO, "무선충전 기능 → 전파법 적합성평가 확인",
             status=ToolStatus.FAILED, error="(더미) 적합성평가 조회 시간 초과"),
        _ran(ToolName.ELECTRICAL, "어댑터 전원 사용 → 전안법 대상 확인", _finding(
            ToolName.ELECTRICAL, "전기용품 안전확인", Determination.REQUIRED, RiskLevel.MEDIUM,
            "직류전원장치 → KC 안전확인 대상", "AC 어댑터 동봉 시 안전확인 필요",
            "전기용품 및 생활용품 안전관리법", "제15조",
        )),
    ], overall=OverallStatus.INSUFFICIENT_INFORMATION,
        summary="전파 분야를 확인하지 못해 판매 전 재확인이 필요합니다.",
        required_actions=["KC 안전확인 신고 (어댑터)"],
        missing_information=["전파 분야 조회에 실패해 적합성평가 대상 여부를 확인하지 못했습니다."],
        incomplete=ExecutionEndReason.RETRY_LIMIT_EXCEEDED)


def _toy_gun(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="어린이 물총 장난감 권총형 대용량", category="완구",
        target_age="만 3세 이상", for_children=True, weapon_like=True,
    )
    return _assessment(product, [
        _ran(ToolName.CHILDREN, "만 3세 이상 완구 → 어린이제품법 대상 확인", _finding(
            ToolName.CHILDREN, "어린이제품 안전확인", Determination.REQUIRED, RiskLevel.HIGH,
            "완구 → 어린이제품 안전확인 필수", "13세 이하 사용 완구는 안전확인 대상", "어린이제품 안전 특별법", "제17조",
        )),
        _ran(ToolName.LABEL_AD, "총 모양 완구 → 표시·광고 검토", _finding(
            ToolName.LABEL_AD, "모의총포 오인 표현", Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM,
            "'실총 같은' 표현은 모의총포 오인 소지", "광고 문구 일부만 검토됨",
            "전자상거래 등에서의 소비자보호에 관한 법률",
        ), status=ToolStatus.PARTIAL),
    ], overall=OverallStatus.HIGH_RISK,
        summary="어린이 완구라 안전확인이 필요하고, 총 모양 표현은 조심해야 합니다.",
        required_actions=["어린이제품 안전확인 신고", "'실총 같은' 광고 문구 삭제"])


def _tumbler(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="스테인리스 진공 텀블러 600ml", category="식기·보온병", food_contact=True,
    )
    return _assessment(product, [
        _ran(ToolName.FOOD_DRUG, "음료가 닿는 용기 → 식품용 기구 확인", _finding(
            ToolName.FOOD_DRUG, "식품용 기구 수입신고", Determination.REQUIRED, RiskLevel.MEDIUM,
            "식품에 닿는 기구 → 판매 목적 수입 시 수입신고 필요", "스테인리스 재질 기준·규격 검사 대상",
            "수입식품안전관리 특별법", "제20조",
        )),
    ], overall=OverallStatus.ACTION_REQUIRED, summary="식품용 기구라 판매 전에 수입신고를 해야 합니다.",
        required_actions=["식품용 기구 수입신고", "재질 기준·규격 검사"])


def _diffuser(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="리드 디퓨저 200ml 무향 베이스", category="방향제", chemical_product=True,
    )
    return _assessment(product, [], overall=OverallStatus.INSUFFICIENT_INFORMATION,
        summary="방향제는 지원하는 분야 밖이라 직접 확인이 필요합니다.",
        missing_information=["생활화학제품(방향제)은 화학제품안전법 확인 대상이며 이 서비스가 지원하지 않습니다."])


def _speaker(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="휴대용 블루투스 스피커 방수 캠핑용", category="스피커",
        electrical_powered=True, wireless_comm=True, battery_included=True,
    )
    return _assessment(product, [
        _ran(ToolName.RADIO, "블루투스 → 전파법 적합성평가 확인", _finding(
            ToolName.RADIO, "전파 적합성평가", Determination.REQUIRED, RiskLevel.HIGH,
            "블루투스 기기 → KC 적합등록 필요", "2.4GHz 무선 송수신", "전파법", "제58조의2",
        )),
        _ran(ToolName.ELECTRICAL, "충전식 배터리 → 전안법 대상 확인", _finding(
            ToolName.ELECTRICAL, "전지 안전확인", Determination.INSUFFICIENT_INFORMATION, RiskLevel.UNKNOWN,
            "내장 전지 용량을 알 수 없어 판단 보류", "전지 용량에 따라 대상 여부가 갈림",
            "전기용품 및 생활용품 안전관리법",
        )),
    ], overall=OverallStatus.ACTION_REQUIRED, summary="블루투스 스피커는 KC 적합등록이 필요합니다.",
        required_actions=["KC 적합등록 (블루투스)"])


def _heating_pad(product_id: str) -> FinalAssessment:
    product = Product(
        product_id=product_id, product_name="USB 온열 방석 3단 온도조절", category="전기방석",
        electrical_powered=True, heating=True,
    )
    return _assessment(product, [], overall=OverallStatus.INSUFFICIENT_INFORMATION, summary="실패 케이스용 결과입니다.")


CASES: dict[DummyCaseName, DummyCase] = {
    DummyCaseName.KC_FAN: DummyCase(rounds=[], fails=False, build=_kc_fan),
    DummyCaseName.POWER_BANK: DummyCase(rounds=[[
        _question("rated_wh", 1, "배터리 정격 용량(Wh)이 표기돼 있나요?", "본체 뒷면의 Wh 또는 mAh·V 표기를 알려 주세요."),
    ]], fails=False, build=_power_bank),
    DummyCaseName.RC_BOAT: DummyCase(rounds=[
        [
            _question("battery_only", 1, "내장 배터리로만 동작하나요?", "배터리 전용이면 안전인증 대상에서 빠질 수 있어요."),
            _question("frequency_band", 2, "무선 주파수 대역이 어떻게 되나요?", "상품 설명이나 본체 라벨의 GHz 표기를 알려 주세요."),
        ],
        [_question("waterproof_rating", 1, "방수 등급(IPX)이 표기돼 있나요?")],
    ], fails=False, build=build_dummy_assessment),
    DummyCaseName.CHARGING_PAD: DummyCase(rounds=[[
        _question("output_watt", 1, "최대 출력(W)이 얼마인가요?"),
        _question("adapter_included", 2, "충전 어댑터가 같이 들어 있나요?"),
    ]], fails=False, build=_charging_pad),
    DummyCaseName.TOY_GUN: DummyCase(rounds=[], fails=False, build=_toy_gun),
    DummyCaseName.TUMBLER: DummyCase(rounds=[
        [_question("inner_coating", 1, "안쪽에 코팅이 돼 있나요?")],
        [_question("steel_grade", 1, "스테인리스 강종(304·316 등)이 표기돼 있나요?")],
    ], fails=False, build=_tumbler),
    DummyCaseName.DIFFUSER: DummyCase(rounds=[], fails=False, build=_diffuser),
    DummyCaseName.QUESTION_LIMIT: DummyCase(rounds=[
        [_question("bluetooth_version", 1, "블루투스 버전이 어떻게 되나요?")],
        [_question("battery_capacity", 1, "내장 배터리 용량이 얼마인가요?")],
        [_question("waterproof_test", 1, "방수 시험 성적서가 있나요?")],
    ], fails=False, build=_speaker),
    DummyCaseName.FAILED: DummyCase(rounds=[], fails=True, build=_heating_pad),
    DummyCaseName.FAILED_AFTER_ANSWER: DummyCase(rounds=[[
        _question("main_user", 1, "주로 누가 사용하나요?", "어린이용이면 어린이제품 기준도 확인해요."),
    ]], fails=True, build=_heating_pad),
}
