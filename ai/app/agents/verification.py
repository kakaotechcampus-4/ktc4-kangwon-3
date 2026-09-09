"""규칙 검사와 모델 검토를 결합해 심사 초안을 검증한다.

``verify(DraftAssessment) -> VerificationResult`` 계약은 그대로 유지한다.
툴 재실행과 재시도 제한은 파이프라인의 책임이며 이 모듈은 판단만 돌려준다.
"""

import json
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

from langchain_core.callbacks import UsageMetadataCallbackHandler

from ..schemas.base import StrictModel, utc_now
from ..schemas.schemas import (
    Determination,
    DraftAssessment,
    FollowUpQuestion,
    RegulatoryFinding,
    ToolName,
    ToolStatus,
    TraceEvent,
    VerificationIssue,
    VerificationIssueType as IssueType,
    VerificationResult,
    VerificationStatus as Status,
)
from ..usage import from_handler, record

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "verification.md"

# 상세 결과의 kind와 툴 종류의 대응. 판별 유니온이 둘의 일치까지 검사하지는 않는다.
_RESULT_KINDS = {
    ToolName.CUSTOMS: "customs",
    ToolName.RADIO: "radio",
    ToolName.FOOD_DRUG: "food_drug",
    ToolName.ELECTRICAL: "electrical",
    ToolName.CHILDREN: "children",
    ToolName.LABEL_AD: "advertising",
}

# 확정적 판단은 실자료 근거가 있어야 한다. 정보 부족·가능성 판단은 대상이 아니다.
_DEFINITIVE = frozenset(
    {Determination.REQUIRED, Determination.NOT_REQUIRED, Determination.NOT_APPLICABLE}
)


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    """고정 시스템 프롬프트를 프로세스에서 한 번만 읽는다."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


class VerificationError(RuntimeError):
    """모델 검증을 완료하지 못했다.

    ``partial_result``에는 모델 호출 전 완료한 규칙 검사 결과를 보존할 수 있다.
    파이프라인은 이를 ``FinalVerificationStatus.INCOMPLETE`` 결과에 포함하고,
    정상 검증 완료로 취급하지 않아야 한다.
    """

    def __init__(
        self,
        message: str,
        *,
        partial_result: VerificationResult | None = None,
    ) -> None:
        super().__init__(message)
        self.partial_result = partial_result


# 모델이 채우는 필드만 담는다. issue_id·question_id·verified_at은 서버가 만든다.
# Structured Outputs의 strict 모드는 모든 필드를 required로 요구하므로 기본값을 두지 않는다.
class _Issue(StrictModel):
    severity: Literal["critical", "warning", "info"]
    issue_type: IssueType
    description: str
    related_finding_ids: list[str]
    recommended_action: str | None


class _Question(StrictModel):
    question: str
    reason: str
    related_tools: list[ToolName]
    required: bool


class _Review(StrictModel):
    # 최종 status와 summary는 규칙 결과와 병합한 뒤 코드가 계산하므로 모델에게 생성시키지 않는다.
    issues: list[_Issue]
    additional_tools_required: list[ToolName]
    follow_up_questions: list[_Question]
    checked_finding_ids: list[str]


class _StructuredModel(Protocol):
    """``model.with_structured_output(...)``이 돌려주는 결과물의 최소 인터페이스."""

    def invoke(self, messages: list, config: dict | None = None) -> _Review: ...


class _ModelLike(Protocol):
    """VerificationAgent가 실제로 쓰는 메서드만 좁혀 놓은 타입.

    ``BaseChatModel``이 이 구조를 만족하므로 실제 모델도 그대로 넘길 수 있고,
    테스트에서는 이를 상속하지 않는 가벼운 스텁도 그대로 넘길 수 있다.
    """

    def with_structured_output(self, schema: type[_Review], **kwargs) -> _StructuredModel: ...


class VerificationAgent:
    """종합된 심사 결과의 근거·누락·모순을 검증한다."""

    def __init__(
        self,
        model: _ModelLike | None = None,
        *,
        configured_model: str | None = None,
    ) -> None:
        # model을 주입하면 테스트에서 실제 API 호출 없이 검증할 수 있다.
        # model 없이도 verify_rules()는 동작하고, verify()는 명시적으로 실패한다.
        self._configured_model = configured_model or getattr(model, "model_name", None)
        self._structured = (
            None
            if model is None
            # 프록시가 strict json_schema를 지원하므로 함수호출 방식 대신 스키마를 강제한다.
            else model.with_structured_output(_Review, method="json_schema", strict=True)
        )

    @classmethod
    def from_env(cls) -> "VerificationAgent":
        from ..config import build_chat_model, load_settings

        settings = load_settings()
        return cls(build_chat_model(settings), configured_model=settings.model)

    def verify(
        self,
        draft: DraftAssessment,
        *,
        trace: list[TraceEvent] | None = None,
    ) -> VerificationResult:
        """규칙 검사와 모델 검토를 합친 검증 결과를 돌려준다.

        ``trace``를 넘기면 스키마 변환과 실행 상태를 ``TraceEvent``로 추가한다.
        상품 원문과 모델 응답 원문은 trace에 저장하지 않는다.

        raises VerificationError: 모델이 없거나, 호출이 실패했거나, 검토 범위가 맞지 않는 경우.
        """
        self._append_trace(
            trace,
            action="verification_started",
            status="started",
            detail=f"DraftAssessment 입력: findings={len(draft.findings)}",
        )
        # 모델 호출 전에 확정적으로 검사할 수 있는 규칙 결과를 먼저 만든다.
        # 이후 모델 단계가 실패해도 이 결과는 VerificationError에 보존된다.
        rules = self.verify_rules(draft, trace=trace)
        if self._structured is None:
            self._append_trace(
                trace,
                action="verification_failed",
                status="failed",
                detail="모델이 없어 전체 검증을 실행하지 못했습니다.",
            )
            raise VerificationError(
                "모델이 없습니다. VerificationAgent.from_env()를 쓰거나, "
                "API 없이 구조만 볼 때는 verify_rules()를 호출하세요.",
                partial_result=rules,
            )
        self._append_trace(
            trace,
            action="model_review_started",
            status="started",
            detail="DraftAssessment를 GPT 구조화 출력 _Review로 검토합니다.",
        )
        usage_handler = UsageMetadataCallbackHandler()
        started_at = perf_counter()
        try:
            review = self._structured.invoke(
                self._build_messages(draft),
                config={"callbacks": [usage_handler]},
            )
        except Exception as exc:
            record(
                "verification",
                from_handler(usage_handler),
                configured_model=self._configured_model,
                subject_id=draft.product.product_id,
                ok=False,
                elapsed_ms=round((perf_counter() - started_at) * 1000),
                error_type=type(exc).__name__,
            )
            self._append_trace(
                trace,
                action="model_review_failed",
                status="failed",
                detail=f"_Review 생성 실패: {type(exc).__name__}",
            )
            # 원인은 __cause__에 그대로 남는다. 응답 본문이 메시지에 섞일 수 있으므로
            # 이 로그를 그대로 외부에 공유하지 않는다.
            raise VerificationError(
                f"모델 검토 호출에 실패했습니다: {type(exc).__name__}: {exc}",
                partial_result=rules,
            ) from exc

        record(
            "verification",
            from_handler(usage_handler),
            configured_model=self._configured_model,
            subject_id=draft.product.product_id,
            elapsed_ms=round((perf_counter() - started_at) * 1000),
        )

        self._append_trace(
            trace,
            action="model_review_completed",
            status="completed",
            detail=(
                f"_Review 생성: issues={len(review.issues)}, "
                f"checked_finding_ids={len(review.checked_finding_ids)}"
            ),
        )
        try:
            self._check_scope(review, draft)
            self._append_trace(
                trace,
                action="scope_validated",
                status="completed",
                detail=f"_Review 검토 범위 확인: findings={len(draft.findings)}",
            )
            result = self._merge(rules, review)
        except VerificationError as exc:
            self._append_trace(
                trace,
                action="review_validation_failed",
                status="failed",
                detail="_Review의 ID 참조 또는 검토 범위가 유효하지 않습니다.",
            )
            raise VerificationError(
                str(exc),
                partial_result=rules,
            ) from exc
        except Exception as exc:
            self._append_trace(
                trace,
                action="result_merge_failed",
                status="failed",
                detail=f"VerificationResult 생성 실패: {type(exc).__name__}",
            )
            raise VerificationError(
                f"모델 검토 결과 처리에 실패했습니다: {type(exc).__name__}",
                partial_result=rules,
            ) from exc

        self._append_trace(
            trace,
            action="result_merged",
            status="completed",
            detail=(
                "규칙 VerificationResult와 _Review를 최종 VerificationResult로 병합: "
                f"status={result.status.value}, issues={len(result.issues)}"
            ),
        )
        self._append_trace(
            trace,
            action="verification_completed",
            status="completed",
            detail=f"VerificationResult 반환: status={result.status.value}",
        )
        return result

    @staticmethod
    def _append_trace(
        trace: list[TraceEvent] | None,
        *,
        action: str,
        status: str,
        detail: str,
    ) -> None:
        """선택적으로 실행 이력을 추가한다. 내부 추론이나 원문 데이터는 기록하지 않는다."""
        if trace is None:
            return
        sequence = trace[-1].sequence + 1 if trace else 1
        trace.append(
            TraceEvent(
                sequence=sequence,
                stage="verification",
                component="VerificationAgent",
                action=action,
                status=status,
                detail=detail,
            )
        )

    def verify_rules(
        self,
        draft: DraftAssessment,
        *,
        trace: list[TraceEvent] | None = None,
    ) -> VerificationResult:
        """구조·근거 유무만 검사한다. API를 호출하지 않는다.

        의미 검증이나 법적 승인을 대신하지 않으므로 이 결과만으로 검증 완료로 쓰면 안 된다.
        """
        self._append_trace(
            trace,
            action="rules_started",
            status="started",
            detail="DraftAssessment 구조와 근거 규칙 검사를 시작합니다.",
        )
        issues: list[VerificationIssue] = []
        tools: list[ToolName] = []

        def add(
            kind: IssueType,
            text: str,
            ids: tuple[str, ...] = (),
            tool: ToolName | None = None,
            severity: Literal["critical", "warning", "info"] = "critical",
        ) -> None:
            issues.append(
                VerificationIssue(
                    severity=severity,
                    issue_type=kind,
                    description=text,
                    related_finding_ids=list(ids),
                    recommended_action="관련 입력과 툴 결과를 보완한 뒤 다시 검증하세요.",
                )
            )
            if tool is not None and tool not in tools:
                tools.append(tool)

        records = {r.tool_name: r for r in draft.tool_results}
        if len(records) != len(draft.tool_results):
            add(IssueType.CONTRADICTION, "같은 툴의 실행 기록이 중복되었습니다.")
        if len(set(draft.selected_tools)) != len(draft.selected_tools):
            add(IssueType.CONTRADICTION, "선택 툴 목록에 중복이 있습니다.")

        for name in ToolName:
            record = records.get(name)
            if record is None:
                add(
                    IssueType.MISSING_TOOL,
                    f"{name}: 선택·미선택 실행 기록이 없습니다.",
                    tool=name if name in draft.selected_tools else None,
                )
                continue
            if record.selected != (name in draft.selected_tools):
                add(
                    IssueType.CONTRADICTION,
                    f"{name}: 선택 목록과 실행 기록의 selected가 다릅니다.",
                )
            if record.selected:
                if record.status != ToolStatus.SUCCESS:
                    add(
                        IssueType.TOOL_FAILURE,
                        f"{name}: 선택된 툴이 성공 상태가 아닙니다.",
                        tool=name,
                    )
                elif record.result is None or not record.findings:
                    add(
                        IssueType.TOOL_FAILURE,
                        f"{name}: 성공 기록에 상세 결과 또는 판단이 없습니다.",
                        tool=name,
                    )
            else:
                # 공통 스키마에 SKIPPED가 생기기 전까지 미선택 상태는
                # NOT_APPLICABLE로 표현한다. 상태가 분리되면 이 규칙도 함께 바꿔야 한다.
                if record.status != ToolStatus.NOT_APPLICABLE:
                    add(
                        IssueType.CONTRADICTION,
                        f"{name}: 미선택 툴의 실행 상태가 not_applicable이 아닙니다.",
                    )
                if record.result is not None or record.findings:
                    add(
                        IssueType.CONTRADICTION,
                        f"{name}: 미선택 툴에 실행 결과 또는 판단이 들어 있습니다.",
                    )
            if record.result is not None and record.result.kind != _RESULT_KINDS[name]:
                add(IssueType.CONTRADICTION, f"{name}: 상세 결과 kind가 툴 종류와 다릅니다.")

        # True인 명시적 신호만 후보 누락 검사에 쓴다. 규제 적용을 확정하는 규칙이 아니다.
        # CUSTOMS와 LABEL_AD는 단순 불리언 하나로 강제하지 않는다. 기본 실행 정책이 필요하면
        # selection·pipeline 담당자와 합의해 별도의 정책으로 추가해야 한다.
        product = draft.product
        signals: dict[ToolName, list[bool | None]] = {
            ToolName.RADIO: [product.wireless_comm, product.wireless_charging],
            ToolName.ELECTRICAL: [
                product.electrical_powered,
                product.battery_included,
                product.battery_is_the_product,
            ],
            ToolName.CHILDREN: [product.for_children],
            ToolName.FOOD_DRUG: [
                product.food_contact,
                product.medical_claim,
                product.cosmetic_claim,
            ],
        }
        for name, values in signals.items():
            if any(v is True for v in values) and name not in draft.selected_tools:
                add(
                    IssueType.MISSING_TOOL,
                    f"{name}: 상품에 검토 신호가 있으나 툴이 선택되지 않았습니다. "
                    "적용 여부를 추가 검토하세요.",
                    tool=name,
                    severity="warning",
                )

        final_ids = [f.finding_id for f in draft.findings]
        if len(final_ids) != len(set(final_ids)):
            add(IssueType.CONTRADICTION, "종합 판단의 finding_id가 중복되었습니다.")
        if not final_ids:
            add(IssueType.MISSING_EVIDENCE, "검증할 종합 판단이 없습니다.")

        # 툴이 만든 원본 판단을 모아 종합 결과와 대조한다.
        original: dict[str, RegulatoryFinding] = {}
        for record in draft.tool_results:
            for finding in record.findings:
                if finding.finding_id in original or finding.tool_name != record.tool_name:
                    add(IssueType.CONTRADICTION, "툴 판단의 ID 중복 또는 소속 툴 불일치가 있습니다.")
                original[finding.finding_id] = finding
        for dropped in sorted(original.keys() - set(final_ids)):
            add(IssueType.CONTRADICTION, f"툴 판단 {dropped}가 종합 결과에서 누락되었습니다.")

        # DraftAssessment.findings는 도구 판단의 출처 보존용 목록이다. aggregate 단계는
        # overall_status·summary·required_actions를 종합하되 원본 finding을 변경하지 않는다.
        # 이 계약을 바꾸려면 원본과 종합 판단을 별도 필드로 분리하는 스키마 합의가 먼저 필요하다.
        for finding in draft.findings:
            fid = finding.finding_id
            if fid not in original or original[fid] != finding:
                add(IssueType.CONTRADICTION, "종합 판단이 원래 툴 판단과 일치하지 않습니다.", (fid,))
            if finding.determination in _DEFINITIVE:
                usable = [
                    s
                    for s in finding.legal_sources
                    if not s.is_mock
                    and (s.quoted_text or "").strip()
                    and (s.source_url or "").strip()
                ]
                if not usable:
                    add(
                        IssueType.MISSING_EVIDENCE,
                        "확정적 판단에 실자료 인용문과 출처가 없습니다. "
                        "mock 자료나 URL만으로는 검증할 수 없습니다.",
                        (fid,),
                        finding.tool_name,
                    )

        result = VerificationResult(
            status=Status.APPROVED,
            issues=issues,
            additional_tools_required=tools,
            # 초안에 이미 있는 사용자 질문도 상태 판단에 함께 반영한다.
            follow_up_questions=list(draft.follow_up_questions),
        )
        result.status = self._status(result)
        result.review_summary = (
            "규칙 검사만 실행했습니다. 모델 의미 검증과 외부 법령 조회는 수행하지 않았습니다."
        )
        # checked_finding_ids는 의미 검토를 마친 모델 결과에서만 채운다.
        self._append_trace(
            trace,
            action="rules_completed",
            status="completed",
            detail=(
                "DraftAssessment -> 규칙 VerificationResult: "
                f"status={result.status.value}, issues={len(result.issues)}"
            ),
        )
        return result

    @staticmethod
    def _build_messages(draft: DraftAssessment) -> list[dict[str, str]]:
        payload = draft.model_dump(mode="json")
        # 조회 파라미터와 원시 응답에는 키·토큰·개인정보가 섞일 수 있어 모델에 보내지 않는다.
        for record in payload["tool_results"]:
            for key in ("query", "raw_response", "error"):
                record.pop(key, None)
        # 출력 JSON Schema는 with_structured_output이 API에 직접 전달한다.
        # 프롬프트에 다시 붙이면 토큰만 늘고 두 스키마가 어긋날 수 있어 넣지 않는다.
        return [
            {"role": "system", "content": _load_system_prompt()},
            {"role": "user", "content": json.dumps({"draft": payload}, ensure_ascii=False)},
        ]

    @staticmethod
    def _check_scope(review: _Review, draft: DraftAssessment) -> None:
        """모델이 모든 판단을 한 번씩 검토했는지, 없는 ID를 만들지 않았는지 확인한다."""
        expected = {f.finding_id for f in draft.findings}
        checked = review.checked_finding_ids
        if len(checked) != len(set(checked)):
            raise VerificationError("checked_finding_ids에 중복이 있습니다.")
        if set(checked) != expected:
            missing = sorted(expected - set(checked))
            unknown = sorted(set(checked) - expected)
            raise VerificationError(
                f"검토 범위가 입력과 다릅니다. 누락 {missing}, 존재하지 않는 ID {unknown}"
            )
        for issue in review.issues:
            unknown = sorted(set(issue.related_finding_ids) - expected)
            if unknown:
                raise VerificationError(f"지적이 존재하지 않는 판단 ID를 참조합니다: {unknown}")

    def _merge(self, rules: VerificationResult, review: _Review) -> VerificationResult:
        """규칙 검사 결과를 모델 검토 위에 덧붙인다. 코드가 찾은 문제는 모델이 지울 수 없다."""
        issues = rules.issues + [VerificationIssue(**i.model_dump()) for i in review.issues]
        tools = list(
            dict.fromkeys(rules.additional_tools_required + review.additional_tools_required)
        )
        # 같은 질문이 규칙과 모델에서 겹치면 하나만 남긴다.
        questions: dict[str, FollowUpQuestion] = {q.question: q for q in rules.follow_up_questions}
        for question in review.follow_up_questions:
            questions.setdefault(question.question, FollowUpQuestion(**question.model_dump()))

        merged = VerificationResult(
            status=Status.APPROVED,
            issues=issues,
            additional_tools_required=tools,
            follow_up_questions=list(questions.values()),
            checked_finding_ids=list(review.checked_finding_ids),
        )
        # 최종 상태와 요약은 병합된 실제 결과를 기준으로 코드가 만든다.
        # 모델 요약을 그대로 쓰면 규칙이 찾은 추가 도구와 모순될 수 있다.
        merged.status = self._status(merged)
        summary_parts = [f"검증 상태 {merged.status.value}, 지적 {len(issues)}건."]
        if tools:
            names = ", ".join(tool.value for tool in tools)
            summary_parts.append(f"추가 검토 도구: {names}.")
        required_questions = sum(question.required for question in merged.follow_up_questions)
        if required_questions:
            summary_parts.append(f"필수 확인 질문: {required_questions}건.")
        if not issues and not tools and not merged.follow_up_questions:
            summary_parts.append("제공된 자료 범위에서 추가 문제를 찾지 못했습니다.")
        summary_parts.append("외부 법령 조회와 현행성 확인은 수행하지 않았습니다.")
        merged.review_summary = " ".join(summary_parts)
        merged.verified_at = utc_now()
        return merged

    @staticmethod
    def _status(result: VerificationResult) -> Status:
        """프롬프트의 우선순위와 같은 순서로 상태를 정한다."""
        if result.additional_tools_required or any(i.severity == "critical" for i in result.issues):
            return Status.REVISION_REQUIRED
        if any(q.required for q in result.follow_up_questions):
            return Status.USER_INPUT_REQUIRED
        if result.issues or result.follow_up_questions:
            return Status.APPROVED_WITH_WARNINGS
        return Status.APPROVED
